"""LoRA adapter library: local inventory + downloads.

The adapters live under LLMOPS_LORA_DIR; each scanned entry's `path` is exactly
what a model's `model_config.lora_modules[].path` should be, so the AddModel
dialog can mount one without the user typing a path.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.auth import require_operator
from app.services import lora_service

router = APIRouter(tags=["lora"])


def _manager(request: Request):
    return request.app.state.lora_download_manager


def _convert_manager(request: Request):
    return request.app.state.lora_convert_manager


class LoraDownloadRequest(BaseModel):
    repo_id: str = Field(min_length=1)
    name: str | None = None  # local folder / served-name default; repo leaf if omitted


class LoraConvertRequest(BaseModel):
    base_model: str | None = None  # override; defaults to the adapter's recorded base
    outtype: str = "f16"           # gguf float type: f16/f32/bf16/q8_0


@router.get("/lora")
async def list_adapters(request: Request):
    """Adapters on disk + free space + whether GGUF conversion is available here."""
    loop = asyncio.get_event_loop()
    adapters = await loop.run_in_executor(None, lora_service.scan)
    disk = await loop.run_in_executor(None, lora_service.disk_usage)
    return {
        "disk": disk,
        "root": lora_service.lora_root(),
        "adapters": adapters,
        "convert_available": _convert_manager(request).available(),
    }


@router.get("/lora/downloads")
async def list_lora_downloads(request: Request):
    return _manager(request).list()


@router.post("/lora/downloads", status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(require_operator)])
async def start_lora_download(body: LoraDownloadRequest, request: Request):
    try:
        return _manager(request).start(body.repo_id, body.name)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/lora/conversions")
async def list_lora_conversions(request: Request):
    mgr = _convert_manager(request)
    return {"available": mgr.available(), "jobs": mgr.list()}


@router.post("/lora/{name}/convert", status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(require_operator)])
async def convert_lora_to_gguf(name: str, body: LoraConvertRequest, request: Request):
    """Convert a PEFT adapter to a GGUF adapter (usable by the llama.cpp engine)."""
    mgr = _convert_manager(request)
    if not mgr.available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "GGUF conversion tooling isn't available on this backend",
        )
    try:
        return mgr.start(name, body.base_model, body.outtype)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.delete("/lora/{name}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_operator)])
async def delete_adapter(name: str, request: Request):
    loop = asyncio.get_event_loop()
    try:
        deleted = await loop.run_in_executor(None, lora_service.delete, name)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except Exception as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"delete failed: {e}")
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no such adapter: {name}")
