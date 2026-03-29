import csv
import io
import json
import logging
import os
import subprocess

import psutil
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()


def get_gpu_info():
    try:
        result = subprocess.check_output(
            [
                'nvidia-smi',
                '--query-gpu=index,name,memory.used,memory.total,utilization.gpu',
                '--format=csv,noheader,nounits'
            ],
            encoding='utf-8'
        )
        lines = result.strip().split('\n')
        gpus = []
        for line in lines:
            index, name, mem_used, mem_total, util = line.split(', ')
            gpus.append({
                "index": int(index),
                "name": name,
                "memory_used": int(mem_used),
                "memory_total": int(mem_total),
                "gpu_util": int(util)
            })
        return gpus
    except Exception as e:
        return []

def get_gpu_processes_with_info():
    cmd = [
        "nvidia-smi",
        "--query-compute-apps=pid,process_name,used_memory",
        "--format=csv,noheader,nounits"
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if result.returncode != 0:
        logger.error("Error: %s", result.stderr)
        return []

    reader = csv.reader(io.StringIO(result.stdout))
    processes = []

    for row in reader:
        if len(row) != 3:
            continue

        pid_str, name, mem_str = row
        pid_str, name, mem_str = pid_str.strip(), name.strip(), mem_str.strip()

        try:
            pid = int(pid_str)
        except ValueError:
            continue

        try:
            used_mem = int(mem_str)
        except ValueError:
            used_mem = None

        process_info = {
            "pid": pid,
            "nvidia_smi_name": name,
            "used_memory_mib": used_mem,
        }

        try:
            p = psutil.Process(pid)
            process_info.update({
                "exe": p.exe(),
                "name": p.name(),
                "cmdline": p.cmdline(),
                "username": p.username()
            })
        except psutil.NoSuchProcess:
            process_info["error"] = "No such process"
        except Exception as e:
            process_info["error"] = str(e)

        processes.append(process_info)
        
    processes_sorted = sorted(
        processes,
        key=lambda x: (x["used_memory_mib"] is None, -(x["used_memory_mib"] or 0))
    )

    return processes_sorted

@router.get("/resources")
def get_system_resources():
    return {
        "cpu": psutil.cpu_percent(interval=0.2),
        "memory": psutil.virtual_memory()._asdict(),
        "gpus": get_gpu_info()
    }

@router.get("/gpu/processes")
def get_gpu_processes():
    json_path = "/app/gpu_status.json"
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="GPU status file not found")
    
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read GPU status: {str(e)}")


