import subprocess
import csv
import io
import psutil


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
            process_info["error"] = "No such process"
        except Exception as e:
            process_info["error"] = str(e)

        processes.append(process_info)
        
    processes_sorted = sorted(
        processes,
        key=lambda x: (x["used_memory_mib"] is None, -(x["used_memory_mib"] or 0))
    )

    return processes_sorted

if __name__ == "__main__":
    processes = get_gpu_processes_with_info()
    print(processes)
