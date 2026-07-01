"""Convert a PEFT LoRA adapter to a GGUF adapter (for the llama.cpp engine).

The dashboard's LoRA library holds HF/PEFT adapters (safetensors folders) that
vLLM/SGLang load directly, but llama.cpp only takes GGUF adapters. This runs
llama.cpp's ``convert_lora_to_gguf.py`` — vendored into the image at a pinned tag
under ``LLMOPS_LORA_CONVERT_DIR`` (see deploy/engine.Dockerfile) — as a subprocess.

The vendored ``gguf-py`` is put on a scoped PYTHONPATH so it never enters the
backend's own site-packages (can't perturb vLLM's deps and always matches the
scripts). torch/transformers/safetensors come from the image. The converter reads
only the base model's **config + tokenizer** (via ``--base-model-id`` → transformers),
not its multi-GB weights, so no large download is needed.

Output ``<name>-<outtype>.gguf`` lands next to the source adapter under the shared
LoRA root, so every backend (incl. llama.cpp) sees it immediately. Async job manager
mirrors LoraDownloadManager.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

from app.services import lora_service

logger = logging.getLogger(__name__)


def convert_dir() -> str:
    return os.environ.get("LLMOPS_LORA_CONVERT_DIR", "/opt/llamacpp-convert")


def convert_available() -> bool:
    """Whether the vendored converter is present (only the vLLM/engine image ships it)."""
    return os.path.isfile(os.path.join(convert_dir(), "convert_lora_to_gguf.py"))


def _adapter_base(folder: str) -> Optional[str]:
    cfg_path = os.path.join(folder, "adapter_config.json")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            return json.load(f).get("base_model_name_or_path")
    except (OSError, json.JSONDecodeError):
        return None


def convert(name: str, base_override: Optional[str] = None, outtype: str = "f16") -> str:
    """Convert PEFT adapter ``<name>`` to a GGUF file; return its path. Blocking.

    Runs the vendored ``convert_lora_to_gguf.py`` with the container's own python
    (torch/transformers/safetensors from the image) and a scoped PYTHONPATH for the
    vendored gguf-py. The base model is resolved by id (``--base-model-id``): its
    config + tokenizer are fetched by transformers, no weights.
    """
    if not convert_available():
        raise RuntimeError(
            "GGUF conversion tooling is not available on this backend "
            "(only the vLLM/engine image vendors it)"
        )
    adapter = lora_service.adapter_dir(name)  # validates name (path traversal guard)
    if not os.path.isdir(adapter):
        raise FileNotFoundError(f"adapter '{name}' not found")
    if not os.path.isfile(os.path.join(adapter, "adapter_config.json")):
        raise ValueError(f"'{name}' is not a PEFT adapter (no adapter_config.json)")

    base_id = (base_override or _adapter_base(adapter) or "").strip()
    if not base_id:
        raise ValueError(
            f"adapter '{name}' records no base_model_name_or_path; specify a base model"
        )

    root = convert_dir()
    out_path = os.path.join(lora_service.lora_root(), f"{name}-{outtype}.gguf")
    # Scope the vendored gguf-py to this subprocess only (never touch site-packages).
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        [os.path.join(root, "gguf-py"), root] + ([existing] if existing else [])
    )
    cmd = [
        sys.executable, os.path.join(root, "convert_lora_to_gguf.py"),
        "--base-model-id", base_id, "--outtype", outtype, "--outfile", out_path, adapter,
    ]
    logger.info("Converting LoRA %s (base=%s) -> %s", name, base_id, out_path)
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip()[-600:]
        raise RuntimeError(f"convert_lora_to_gguf failed (rc={proc.returncode}): {tail}")
    if not os.path.isfile(out_path):
        raise RuntimeError("conversion reported success but produced no .gguf")
    return out_path


@dataclass
class LoraConvertJob:
    name: str          # source PEFT adapter name
    base_model: Optional[str] = None
    outtype: str = "f16"
    state: str = "pending"  # pending | converting | completed | failed
    out_path: Optional[str] = None
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class LoraConvertManager:
    """In-memory PEFT->GGUF conversion jobs, keyed by source adapter name."""

    def __init__(self) -> None:
        self._jobs: dict[str, LoraConvertJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def available(self) -> bool:
        return convert_available()

    def list(self) -> list[dict]:
        return [asdict(j) for j in sorted(self._jobs.values(), key=lambda j: j.started_at, reverse=True)]

    def start(self, name: str, base_model: Optional[str] = None, outtype: str = "f16") -> dict:
        name = (name or "").strip()
        lora_service.adapter_dir(name)  # validate early (raises on traversal/garbage)
        existing = self._jobs.get(name)
        if existing and existing.state in ("pending", "converting"):
            return asdict(existing)  # already in flight — idempotent
        job = LoraConvertJob(name=name, base_model=(base_model or None), outtype=outtype)
        self._jobs[name] = job
        self._tasks[name] = asyncio.create_task(self._run(job))
        return asdict(job)

    async def _run(self, job: LoraConvertJob) -> None:
        loop = asyncio.get_event_loop()
        job.state = "converting"
        job.updated_at = time.time()
        try:
            job.out_path = await loop.run_in_executor(
                None, convert, job.name, job.base_model, job.outtype
            )
            job.state = "completed"
            logger.info("Converted LoRA %s -> %s", job.name, job.out_path)
        except Exception as e:
            job.state = "failed"
            job.error = str(e)
            logger.warning("LoRA GGUF conversion failed for %s: %s", job.name, e)
        finally:
            job.updated_at = time.time()
            self._tasks.pop(job.name, None)
