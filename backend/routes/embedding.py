from app.launcher.embedding_launcher import (launch_embedding_server,
                                             stop_embedding_server)
from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/embedding/start")
def start_embedding_server(request: Request):
    config_path = request.app.state.config_path 
    app = request.app
    app.state.starting_models.add("Embedding & reranking Server")
    try:
        launch_embedding_server(config_path)
        return {"status": "啟動中", "message": "Embedding Server 已啟動"}
    except Exception as e:
        return {"status": "錯誤", "message": str(e)}
    finally:
        app.state.starting_models.discard("Embedding & reranking Server")
    
@router.post("/embedding/stop")
def stop_embedding():
    try:
        stop_embedding_server()
        return {"status": "未啟動", "message": "Embedding Server 已關閉"}
    except Exception as e:
        return {"status": "錯誤", "message": str(e)}