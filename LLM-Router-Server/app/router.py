import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

router = APIRouter()

@router.post("/v1/chat/completions")
async def proxy_chat_completion(request: Request):
    try:
        config = request.app.state.config
        request_json = await request.json()
        model_key = request_json.get("model")

        model_cfg = config["LLM_engines"].get(model_key)
        if not model_cfg:
            raise HTTPException(status_code=404, detail=f"Model '{model_key}' not found.")

        model_tag = model_cfg["model_tag"]
        request_json["model"] = model_tag
        host = model_cfg.get("host", "localhost")
        port = model_cfg["port"]
        target_url = f"http://{host}:{port}/v1/chat/completions"

        client = request.app.state.http_client
        stream_ctx = client.stream("POST", target_url, json=request_json)
        response = await stream_ctx.__aenter__()

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            async def event_stream():
                try:
                    async for chunk in response.aiter_raw():
                        yield chunk
                finally:
                    await stream_ctx.__aexit__(None, None, None)

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        content = await response.aread()
        await stream_ctx.__aexit__(None, None, None)
        return Response(
            content=content,
            status_code=response.status_code,
            media_type="application/json"  
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
@router.get("/v1/models")
async def list_models(request: Request):
    config = request.app.state.config
    engines = config.get("LLM_engines", {})

    model_list = [
        {"id": model_key, "object": "model"}
        for model_key in engines.keys()
    ]

    return JSONResponse(
        content={
            "object": "list",
            "data": model_list
        }
    )

@router.post("/v1/completions")
async def proxy_completion(request: Request):
    try:
        config = request.app.state.config
        request_json = await request.json()
        model_key = request_json.get("model")

        if not model_key:
            raise HTTPException(status_code=400, detail="Missing 'model' field in request body")

        model_cfg = config.get("LLM_engines", {}).get(model_key)
        if not model_cfg:
            raise HTTPException(status_code=404, detail=f"Model '{model_key}' not found in config")

        model_tag = model_cfg["model_tag"]
        request_json["model"] = model_tag

        host = model_cfg.get("host", "localhost") 
        port = model_cfg["port"]
        target_url = f"http://{host}:{port}/v1/completions"

        client = request.app.state.http_client
        stream_ctx = client.stream("POST", target_url, json=request_json)
        response = await stream_ctx.__aenter__()

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            async def event_stream():
                try:
                    async for chunk in response.aiter_raw():
                        yield chunk
                finally:
                    await stream_ctx.__aexit__(None, None, None)

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        content = await response.aread()
        await stream_ctx.__aexit__(None, None, None)
        return Response(
            content=content,
            status_code=response.status_code,
            media_type="application/json"  
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
    
@router.post("/v1/embeddings")
async def proxy_embeddings(request: Request):
    try:
        config = request.app.state.config
        embedding_cfg = config.get("embedding_server", {})
        host = embedding_cfg.get("host", "localhost")
        port = embedding_cfg.get("port", 8003)
        target_url = f"http://{host}:{port}/v1/embeddings"

        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        client = request.app.state.http_client
        resp = await client.post(
                target_url,
                content=body,
                headers=headers
            )

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers)
        )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503, detail=f"Cannot connect to embedding server: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Unexpected error: {str(e)}"
        )