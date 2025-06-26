import subprocess
import csv
import io
import psutil
import json
import time


def get_username_from_ps(pid):
    try:
        result = subprocess.run(
            ["ps", "-o", "user=", "-p", str(pid)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return None
    except Exception:
        return None


def get_gpu_processes_with_info():
    cmd = [
        "nvidia-smi",
        "--query-compute-apps=pid,process_name,used_memory",
        "--format=csv,noheader,nounits"
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    if result.returncode != 0:
        print("Error:", result.stderr)
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

        # 基本資料
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
            username = get_username_from_ps(pid)
            if username:
                process_info["username"] = username
                process_info["error"] = "psutil failed, fallback to ps"
            else:
                process_info["error"] = "No such process"
        except psutil.AccessDenied:
            username = get_username_from_ps(pid)
            if username:
                process_info["username"] = username
                process_info["error"] = "Access denied, fallback to ps"
            else:
                process_info["error"] = "Access denied"


        processes.append(process_info)
    
    processes_sorted = sorted(
        processes,
        key=lambda x: (x['used_memory_mib'] is None, -(x['used_memory_mib'] or 0))
    )

    return processes_sorted

if __name__ == "__main__":
    while True:
        print("Fetching GPU processes...")
        processes = get_gpu_processes_with_info()
        with open('/data/max.dh.kuo_data/gpu_status.json', 'w') as f:
            json.dump(processes, f, indent=4)
        time.sleep(10)

