import asyncio
import logging

import httpx
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/status/all")
async def get_all_model_status(request: Request):
    config = request.app.state.config
    http_client = request.app.state.http_client
    starting_models = getattr(request.app.state, "starting_models", set())
    llm_engines = config.get("LLM_engines", {})
    embedding = config.get("embedding_server", None)

    tasks = []

    async def check_status(name: str, host: str, port: int):
        url = f"http://{host}:{port}/health"
        if name in starting_models:
            return {"name": name, "status": "啟動中", "port": port}
        try:
            resp = await http_client.get(url)
            if resp.status_code == 200:
                return {"name": name, "status": "已啟動", "port": port}
        except Exception:
            logger.error(f"無法連接模型 {name} : {url}")
        return {"name": name, "status": "未啟動", "port": port}
          
    for name, cfg in llm_engines.items():
        instances = cfg.get("instances", [])
        for instance in instances:
            instance_id = instance.get("id")
            if instance_id:
                host = instance.get("host", cfg.get("host", "localhost"))
                port = instance.get("port", cfg.get("port"))
                if port:
                    tasks.append(check_status(f"{name}::{instance_id}", host, port))

    if embedding:
        host = embedding.get("host", "localhost")
        port = embedding.get("port")
        if port:
            tasks.append(check_status("Embedding & reranking Server", host, port))

    results = await asyncio.gather(*tasks)
    return {"models": results}

