import copy
import json
import os
import subprocess
from typing import Dict
import time

import yaml

running_llm_procs: Dict[str, subprocess.Popen] = {}

def wait_for_model_ready(log_path: str, timeout: int = 300, model_name: str = "") -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                logs = f.read()
                if all(kw in logs for kw in [
                    "Started server process",
                    "Waiting for application startup.",
                    "Application startup complete."
                ]):
                    print(f"模型 {model_name} 啟動完成")
                    return True
                if "Traceback" in logs:
                    print(f"模型 {model_name} 啟動失敗，請檢查日誌：{log_path}")
                    return False
        print(f"檢查中：{model_name} 尚未啟動完成，等待中...")
        time.sleep(10)

    print(f"模型 {model_name} 啟動逾時，請檢查日誌：{log_path}")
    return False

def build_cli_args_from_dict(model_cfg: dict) -> list:
    model_tag = model_cfg.get("model_tag")
    if not model_tag:
        raise ValueError("必須提供 model_tag")
    
    cli_args = ["serve", model_tag]

    for key, value in model_cfg.items():
        if key == "model_tag" or value is None:
            continue
        key_flag = "--" + key.replace("_", "-")
        if isinstance(value, bool):
            if value:
                cli_args.append(key_flag)
        elif isinstance(value, list):
            cli_args.append(key_flag)
            cli_args.append(json.dumps(value))
        else:
            cli_args.append(key_flag)
            cli_args.append(str(value))

    return cli_args

def launch_single_llm_model(model_name: str, config_path: str):
    ## 應該要透過檢查log檢查是否有成功啟動
    global running_llm_procs
    if model_name in running_llm_procs and running_llm_procs[model_name].poll() is None:
        print(f"模型 {model_name} 已經在執行中，跳過啟動。")
        raise RuntimeError(f"模型 {model_name} 已在執行中，請勿重複啟動。")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    engines = config.get("LLM_engines", {})
    if model_name not in engines:
        raise ValueError(f"模型 {model_name} 未在配置中找到。")
    
    model_cfg = copy.deepcopy(engines[model_name])
    cuda_id = None
    if model_cfg.get("tensor_parallel_size", 1) == 1:
        cuda_id = model_cfg.pop("cuda_device", None)
    cli_args = build_cli_args_from_dict(model_cfg)
    cuda_env = os.environ.copy()
    if cuda_id is not None:
        cuda_env["CUDA_VISIBLE_DEVICES"] = str(cuda_id)
        print(f"設定 {model_name} 使用 GPU {cuda_id}")
    # set vllm
    if "VLLM_WORKER_MULTIPROC_METHOD" not in cuda_env:
        print("設定 VLLM_WORKER_MULTIPROC_METHOD 為 'spawn'")
        cuda_env["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"
    cuda_env["TORCH_CUDA_ARCH_LIST"] = "8.0"
    log_path = f"./logs/{model_name}.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        f.truncate(0)
    with open(log_path, "w", encoding="utf-8") as log_file:
        try:
            print(f"執行指令: vllm {' '.join(cli_args)}")
            proc = subprocess.Popen(
                ["vllm"] + cli_args,
                env=cuda_env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )
            running_llm_procs[model_name] = proc
            print(f"{model_name} 啟動中 (PID={proc.pid})")
            
        except Exception as e:
            print(f"啟動模型 {model_name} 失敗: {e}")
            raise
        if not wait_for_model_ready(log_path, timeout=300, model_name=model_name):
            raise RuntimeError(f"模型 {model_name} 啟動失敗，請檢查日誌 {log_path}")
        time.sleep(5)
        if proc.poll() is not None:
            raise RuntimeError(f"模型 {model_name} 啟動失敗，請檢查日誌檔案 {log_path}。")
    
    
def stop_single_llm_model(model_name: str):
    global running_llm_procs

    proc = running_llm_procs.get(model_name)
    if proc and proc.poll() is None:
        print(f"關閉模型 {model_name} (PID={proc.pid})")
        proc.terminate()
        proc.wait(timeout=5)
        del running_llm_procs[model_name]
    else:
        print(f"模型 {model_name} 沒有在執行中。")        