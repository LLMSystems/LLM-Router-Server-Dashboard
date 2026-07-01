import asyncio
import json

import pytest

from app.services import lora_convert

pytestmark = pytest.mark.unit


def _peft(root, name, base="Qwen/Qwen3-0.6B"):
    d = root / name
    d.mkdir(parents=True)
    (d / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": base, "r": 8}))
    (d / "adapter_model.safetensors").write_bytes(b"\0" * 16)
    return d


def test_convert_available_reflects_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMOPS_LORA_CONVERT_DIR", str(tmp_path))
    assert lora_convert.convert_available() is False
    (tmp_path / "convert_lora_to_gguf.py").write_text("# vendored")
    assert lora_convert.convert_available() is True


def test_convert_reads_base_from_adapter_config(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMOPS_LORA_DIR", str(tmp_path))
    _peft(tmp_path, "my-lora", base="org/BaseModel")
    assert lora_convert._adapter_base(str(tmp_path / "my-lora")) == "org/BaseModel"


def test_convert_raises_when_tooling_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMOPS_LORA_DIR", str(tmp_path))
    monkeypatch.setenv("LLMOPS_LORA_CONVERT_DIR", str(tmp_path / "no-tooling"))
    _peft(tmp_path, "my-lora")
    with pytest.raises(RuntimeError, match="not available"):
        lora_convert.convert("my-lora")


def test_convert_requires_a_base(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMOPS_LORA_DIR", str(tmp_path))
    monkeypatch.setenv("LLMOPS_LORA_CONVERT_DIR", str(tmp_path))
    (tmp_path / "convert_lora_to_gguf.py").write_text("# vendored")
    d = tmp_path / "no-base"
    d.mkdir()
    (d / "adapter_config.json").write_text(json.dumps({"r": 8}))  # no base_model
    with pytest.raises(ValueError, match="base"):
        lora_convert.convert("no-base")


def test_manager_start_is_idempotent_and_reports_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMOPS_LORA_DIR", str(tmp_path))
    _peft(tmp_path, "my-lora")

    calls = {"n": 0}

    def fake_convert(name, base, outtype):
        calls["n"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(lora_convert, "convert", fake_convert)

    async def run():
        mgr = lora_convert.LoraConvertManager()
        j1 = mgr.start("my-lora")
        j2 = mgr.start("my-lora")  # in-flight -> same job, no second task
        assert j1["name"] == j2["name"]
        # let the task run
        for _ in range(20):
            await asyncio.sleep(0.01)
            job = mgr.list()[0]
            if job["state"] in ("completed", "failed"):
                break
        job = mgr.list()[0]
        assert job["state"] == "failed" and "boom" in job["error"]
        assert calls["n"] == 1  # idempotent: only one conversion ran

    asyncio.run(run())
