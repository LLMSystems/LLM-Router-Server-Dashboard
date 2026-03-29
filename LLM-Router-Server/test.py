# from src.llm_router.vllm_metrics_client import VLLMMetricsClient



# if __name__ == "__main__":
#     import asyncio
    
#     client = VLLMMetricsClient()
#     metrics = asyncio.run(client.fetch("http://localhost:8002"))
#     print(metrics.base_url)
#     print(metrics.running)
#     print(metrics.waiting)
#     print(metrics.kv_cache_usage_perc)
#     print(metrics.prompt_tokens)
#     print(metrics.generation_tokens)

from src.llm_router.config_loader import load_config
from src.llm_router.vllm_launcher import build_cli_args_from_dict
import os
from typing import Dict
from src.llm_router.env import env_setup
from vllm.logger import init_logger
import copy
import time
import subprocess

logger = init_logger(__name__)

running_processes: Dict[str, subprocess.Popen] = {}

def wait_for_model_ready(log_path, timeout=600, model_name=""):
    start_time = time.time()
    last_log_time = 0
    while time.time() - start_time < timeout:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                logs = f.read()
                if ("Started server process" in logs and
                    "Waiting for application startup." in logs and
                    "Application startup complete." in logs):
                    logger.info(f"{model_name} 已偵測到完整啟動訊號。")
                    return True
        if time.time() - last_log_time > 10:
            logger.info(f"仍在等待 {model_name} 啟動中...")
            last_log_time = time.time()
        time.sleep(2)
    return False


if __name__ == "__main__":
    """
    LLM_engines:
    Qwen2.5-1.5B-Instruct-GPTQ-Int4:
        routing:
        strategy: least_load

        instances:
        - id: "qwen15b-a"
            host: "localhost"
            port: 8001
            cuda_device: 0

        - id: "qwen15b-b"
            host: "localhost"
            port: 8003
            cuda_device: 1

        model_config:
        model_tag: "Qwen/Qwen2.5-1.5B-Instruct-GPTQ-Int4"
        dtype: "float16"
        max_model_len: 2000
        gpu_memory_utilization: 0.3
        max_num_seqs: 1
        quantization: "gptq"
        tensor_parallel_size: 1


    Qwen3-0.6B:
        routing:
        strategy: least_load

        instances:
        - id: "qwen3"
            host: "localhost"
            port: 8002
            cuda_device: 0
        - id: "qwen3-2"
            host: "localhost"
            port: 8004
            cuda_device: 1

        model_config:
        model_tag: "Qwen/Qwen3-0.6B"
        dtype: "float16"
        max_model_len: 10000
        gpu_memory_utilization: 0.3
        max_num_seqs: 200
        tensor_parallel_size: 1
        enable_auto_tool_choice: true
        tool-call-parser: "hermes"
    """
    env_setup()
    config = load_config("./configs/configV2.yaml")
    engines = config.get("LLM_engines", {})
    
    for model_name, model_group_cfg in engines.items():
        try:
            instances = model_group_cfg.get("instances", [])
            shared_model_cfg = model_group_cfg.get("model_config", {})
            if not instances:
                logger.info(f"Model group '{model_name}' has no instances defined.")
                continue
            logger.info(f"Model group '{model_name}' has {len(instances)} instance(s).")
            
            for instance in instances:
                try:
                    instance_id = instance.get("id")
                    if not instance_id:
                        raise ValueError(f"{model_name} 的 instance 缺少 id 欄位")
                    merged_cfg = copy.deepcopy(shared_model_cfg)
                    merged_cfg.update(copy.deepcopy(instance))
                    
                    cuda_id = None
                    if merged_cfg.get("tensor_parallel_size", 1) == 1:
                        cuda_id = merged_cfg.pop("cuda_device", None)
                        
                    # pop id
                    merged_cfg.pop("id", None)

                    cli_args = build_cli_args_from_dict(merged_cfg)

                    logger.info(
                        f"執行指令 [{model_name}/{instance_id}]: vllm {' '.join(cli_args)}"
                    )
                    cuda_env = os.environ.copy()
                    if cuda_id is not None:
                        cuda_env["CUDA_VISIBLE_DEVICES"] = str(cuda_id)
                        logger.info(
                            f"設定 {model_name}/{instance_id} 使用 GPU {cuda_id}"
                        )

                    log_path = f"./logs/{model_name}__{instance_id}.log"
                    os.makedirs(os.path.dirname(log_path), exist_ok=True)
                    
                    if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
                        logger.info(
                            f"{model_name}/{instance_id} 的 log 檔案已存在且不為空，將清空。"
                        )
                        with open(log_path, "w", encoding="utf-8") as f:
                            f.truncate(0)

                    with open(log_path, "w", encoding="utf-8") as log_file:
                        proc = subprocess.Popen(
                            ["vllm"] + cli_args,
                            env=cuda_env,
                            stdout=log_file,
                            stderr=subprocess.STDOUT,
                            start_new_session=True,
                        )

                    process_key = f"{model_name}::{instance_id}"
                    running_processes[process_key] = proc

                    logger.info(f"等待 {model_name}/{instance_id} 啟動完成...")
                    if wait_for_model_ready(log_path, model_name=f"{model_name}/{instance_id}"):
                        logger.info(f"{model_name}/{instance_id} 啟動完成。")
                    else:
                        logger.warning(f"{model_name}/{instance_id} 啟動超時，可能啟動失敗。")

                except Exception as e:
                    logger.error(f"處理 {model_name} 的 instance 時發生錯誤: {e}")
        except Exception as e:
            logger.error(f"處理模型群組 {model_name} 時發生錯誤: {e}")