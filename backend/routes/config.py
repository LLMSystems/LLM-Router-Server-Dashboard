from pathlib import Path

import yaml
from fastapi import APIRouter

router = APIRouter()

@router.get("/config")
def get_config():
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)
        
    llm_engines = {}
    
    for name, cfg in raw_config.get("LLM_engines", {}).items():
        instances = cfg.get("instances", [])
        shared_model_cfg = cfg.get("model_config", {})
        if instances:
            for instance in instances:
                instance_id = instance.get("id")
                if instance_id:
                    key = f"{name}::{instance_id}"
                    llm_engines[key] = {
                        "port": instance.get("port", cfg.get("port")),
                        "cuda_device": instance.get("cuda_device", cfg.get("cuda_device")),
                        "max_model_len": shared_model_cfg.get("max_model_len", cfg.get("max_model_len")),
                        "gpu_memory_utilization": shared_model_cfg.get("gpu_memory_utilization", cfg.get("gpu_memory_utilization")),
                        "tool_parser": shared_model_cfg.get("tool-call-parser") or instance.get("reasoning_parser") or cfg.get("tool-call-parser") or cfg.get("reasoning_parser") or "unknown"
                    }
                else:
                    continue

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
