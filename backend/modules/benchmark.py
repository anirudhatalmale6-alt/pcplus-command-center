import asyncio
import re

SERVERS = {
    "server18": {"host": "127.0.0.1", "port": None, "name": "Server 18 (RMM/Mesh/Zammad)", "key": None},
}

SERVICE_GROUPS = {
    "Tactical RMM": ["uwsgi", "uvicorn.*tacticalrmm", "celery.*tacticalrmm", "nats-server"],
    "MeshCentral": ["node.*meshcentral"],
    "Zammad": ["puma.*zammad", "background-worker.rb", "websocket-server.rb"],
    "Wazuh": ["wazuh-", "ossec"],
    "Elasticsearch": ["elasticsearch", "java.*elasticsearch"],
    "Wazuh Indexer": ["wazuh-indexer", "java.*wazuh-indexer"],
    "Grafana": ["grafana"],
    "PostgreSQL": ["postgres:"],
    "Redis": ["redis-server"],
    "Nginx": ["nginx"],
    "PC Plus Dashboard": ["PCPlusDashboard"],
    "Command Center": ["uvicorn.*command"],
    "Cal.com": ["next-server"],
    "AdGuard Home": ["AdGuardHome"],
    "OpenVAS/GVM": ["gvmd", "ospd-openvas", "openvas"],
    "Docker": ["dockerd", "containerd"],
}


async def _run_cmd(cmd: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
    return stdout.decode(errors="replace")


async def get_server_benchmark():
    try:
        lines = await _run_cmd(
            "ps aux --no-headers --sort=-%mem"
        )
        mem_info = await _run_cmd("free -b")
        cpu_info = await _run_cmd(
            "head -1 /proc/stat && sleep 1 && head -1 /proc/stat"
        )
        load_info = await _run_cmd("cat /proc/loadavg")
        disk_info = await _run_cmd("df -B1 / 2>/dev/null")
        uptime_info = await _run_cmd("cat /proc/uptime")

        # Parse memory
        mem_lines = mem_info.strip().split("\n")
        mem_total = mem_used = mem_available = 0
        swap_total = swap_used = 0
        for ml in mem_lines:
            parts = ml.split()
            if parts[0] == "Mem:":
                mem_total = int(parts[1])
                mem_used = int(parts[2])
                mem_available = int(parts[6]) if len(parts) > 6 else mem_total - mem_used
            elif parts[0] == "Swap:":
                swap_total = int(parts[1])
                swap_used = int(parts[2])

        # Parse CPU usage
        cpu_percent = 0.0
        cpu_lines_list = cpu_info.strip().split("\n")
        if len(cpu_lines_list) >= 2:
            c1 = [int(x) for x in cpu_lines_list[0].split()[1:]]
            c2 = [int(x) for x in cpu_lines_list[1].split()[1:]]
            idle1, idle2 = c1[3], c2[3]
            total1, total2 = sum(c1), sum(c2)
            diff_idle = idle2 - idle1
            diff_total = total2 - total1
            if diff_total > 0:
                cpu_percent = round((1 - diff_idle / diff_total) * 100, 1)

        # Parse load
        load_parts = load_info.strip().split()
        load_1 = float(load_parts[0]) if load_parts else 0
        load_5 = float(load_parts[1]) if len(load_parts) > 1 else 0
        load_15 = float(load_parts[2]) if len(load_parts) > 2 else 0

        # Parse disk
        disk_total = disk_used = disk_avail = 0
        disk_lines = disk_info.strip().split("\n")
        if len(disk_lines) > 1:
            dp = disk_lines[1].split()
            disk_total = int(dp[1])
            disk_used = int(dp[2])
            disk_avail = int(dp[3])

        # Parse uptime
        uptime_secs = float(uptime_info.strip().split()[0]) if uptime_info.strip() else 0

        # Group processes by service
        services = {}
        ungrouped_procs = []

        for line in lines.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            try:
                cpu = float(parts[2])
                mem = float(parts[3])
                rss_kb = int(parts[5])
                cmd_str = parts[10]
            except (ValueError, IndexError):
                continue

            matched = False
            for svc_name, patterns in SERVICE_GROUPS.items():
                for pat in patterns:
                    if re.search(pat, cmd_str, re.IGNORECASE):
                        if svc_name not in services:
                            services[svc_name] = {
                                "cpu": 0.0, "mem_mb": 0, "mem_pct": 0.0,
                                "processes": 0, "pids": []
                            }
                        services[svc_name]["cpu"] = round(services[svc_name]["cpu"] + cpu, 1)
                        services[svc_name]["mem_mb"] += rss_kb // 1024
                        services[svc_name]["mem_pct"] = round(services[svc_name]["mem_pct"] + mem, 1)
                        services[svc_name]["processes"] += 1
                        matched = True
                        break
                if matched:
                    break

            if not matched and (cpu > 0.5 or rss_kb > 50000):
                proc_name = parts[10].split("/")[-1].split()[0][:30]
                ungrouped_procs.append({
                    "name": proc_name,
                    "cpu": cpu,
                    "mem_mb": rss_kb // 1024,
                })

        # Sort services by memory
        sorted_services = dict(
            sorted(services.items(), key=lambda x: x[1]["mem_mb"], reverse=True)
        )

        return {
            "server": {
                "name": "Server 18 (RMMSRVT)",
                "cpu_model": "AMD Ryzen 9 3900XT",
                "cores": 24,
                "ram_total_gb": round(mem_total / (1024**3), 1),
                "ram_used_gb": round(mem_used / (1024**3), 1),
                "ram_available_gb": round(mem_available / (1024**3), 1),
                "ram_pct": round(mem_used / mem_total * 100, 1) if mem_total else 0,
                "swap_total_gb": round(swap_total / (1024**3), 1),
                "swap_used_gb": round(swap_used / (1024**3), 1),
                "cpu_pct": cpu_percent,
                "load_1": load_1,
                "load_5": load_5,
                "load_15": load_15,
                "disk_total_gb": round(disk_total / (1024**3), 1),
                "disk_used_gb": round(disk_used / (1024**3), 1),
                "disk_pct": round(disk_used / disk_total * 100, 1) if disk_total else 0,
                "uptime_days": round(uptime_secs / 86400, 1),
            },
            "services": sorted_services,
            "other_processes": sorted(ungrouped_procs, key=lambda x: x["mem_mb"], reverse=True)[:10],
        }
    except Exception:
        return {"server": {}, "services": {}, "other_processes": []}
