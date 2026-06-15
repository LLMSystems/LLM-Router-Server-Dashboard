"""Accuracy / quality evaluation (evalscope run_task) endpoints."""
from __future__ import annotations

import os
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.auth import require_admin
from app.eval.manager import EvalBusy, EvalError
from app.services.dataset_service import EVAL_CATALOG

router = APIRouter(prefix="/eval", tags=["eval"])


def _em(request: Request):
    return request.app.state.eval_manager


def _store(request: Request):
    return request.app.state.store


class EvalRequest(BaseModel):
    model: str  # model group
    name: Optional[str] = None
    target: Literal["router", "instance"] = "router"
    instance_key: Optional[str] = None
    datasets: list[str] = Field(min_length=1)
    limit: Optional[int] = Field(default=10, ge=1)  # None = full dataset
    repeats: int = Field(default=1, ge=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2048, ge=1)
    eval_batch_size: int = Field(default=8, ge=1)
    timeout: int = Field(default=600, ge=1)
    stream: bool = True


@router.get("/datasets")
async def list_eval_datasets():
    """Curated evalscope benchmark catalog, grouped by capability tier."""
    return {"datasets": EVAL_CATALOG}


@router.get("")
async def list_runs(request: Request, limit: int = 50):
    return {"busy": _em(request).busy, "runs": await _store(request).list_eval_runs(limit)}


@router.post("", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_admin)])
async def start_run(body: EvalRequest, request: Request):
    known = {d["key"] for d in EVAL_CATALOG}
    unknown = [d for d in body.datasets if d not in known]
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown dataset(s): {unknown}")
    # A load test and an eval both saturate the same model — don't let them overlap.
    if request.app.state.perf_manager.busy:
        raise HTTPException(status.HTTP_409_CONFLICT, "a load test is running; try again later")
    try:
        return await _em(request).start(body.model_dump())
    except EvalBusy as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    except EvalError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/{run_id}")
async def get_run(run_id: int, request: Request):
    run = await _store(request).get_eval_run(run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown eval run: {run_id}")
    return run


@router.get("/{run_id}/log")
async def get_run_log(run_id: int, request: Request, tail: int = 200):
    run = await _store(request).get_eval_run(run_id)
    if run is None or not run.get("output_dir"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown eval run: {run_id}")
    path = os.path.join(run["output_dir"], "run.log")
    if not os.path.exists(path):
        return {"content": ""}
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return {"content": "".join(lines[-tail:])}


@router.get("/{run_id}/report", response_class=FileResponse)
async def get_run_report(run_id: int, request: Request):
    """The full evalscope interactive HTML report for a run."""
    run = await _store(request).get_eval_run(run_id)
    if run is None or not run.get("output_dir"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown eval run: {run_id}")
    path = os.path.join(run["output_dir"], "reports", "report.html")
    if not os.path.exists(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not available for this run")
    return FileResponse(path, media_type="text/html")


@router.post("/{run_id}/cancel", dependencies=[Depends(require_admin)])
async def cancel_run(run_id: int, request: Request):
    if not await _em(request).cancel(run_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "run is not active")
    return {"ok": True}


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_admin)])
async def delete_run(run_id: int, request: Request):
    if not await _store(request).delete_eval_run(run_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown eval run: {run_id}")
