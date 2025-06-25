from fastapi import APIRouter, Request
import httpx
import asyncio

router = APIRouter()

@router.get("/status/all")
async def get_all_model_status(request: Request):
    config = request.app.state.config
    starting_models = getattr(request.app.state, "starting_models", set())
    llm_engines = config.get("LLM_engines", {})
    embedding = config.get("embedding_server", None)

    tasks = []

    async def check_status(name: str, host: str, port: int):
        url = f"http://{host}:{port}/health"
        if name in starting_models:
            return {"name": name, "status": "啟動中", "port": port}
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return {"name": name, "status": "已啟動", "port": port}
        except Exception:
            print(f"無法連接模型 {name} : {url}")
        return {"name": name, "status": "未啟動", "port": port}

    for name, cfg in llm_engines.items():
        host = cfg.get("host", "localhost")
        port = cfg.get("port")
        if port:
            tasks.append(check_status(name, host, port))

    if embedding:
        host = embedding.get("host", "localhost")
        port = embedding.get("port")
        if port:
            tasks.append(check_status("Embedding & reranking Server", host, port))

    results = await asyncio.gather(*tasks)
    return {"models": results}

