from fastapi import APIRouter
import yaml
from pathlib import Path

router = APIRouter()

@router.get("/config")
def get_config():
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    llm_engines = {
        name: {
            "port": cfg["port"],
            "cuda_device": cfg.get("cuda_device"),
            "max_model_len": cfg.get("max_model_len"),
            "gpu_memory_utilization": cfg.get("gpu_memory_utilization"),
            "tool_parser": cfg.get("tool-call-parser") or cfg.get("reasoning_parser") or "unknown"
        }
        for name, cfg in raw_config.get("LLM_engines", {}).items()
    }

    embedding_server = raw_config.get("embedding_server", {})
    embedding_summary = {
        "port": embedding_server.get("port"),
        "cuda_device": embedding_server.get("cuda_device"),
        "embedding_models": list(embedding_server.get("embedding_models").keys()) if embedding_server.get("embedding_models") else [],
        "reranking_models": list(embedding_server.get("reranking_models").keys()) if embedding_server.get("reranking_models") else [],
    }


    return {
        "server": raw_config.get("server", {}),
        "LLM_engines": llm_engines,
        "embedding_server": embedding_summary
    }
