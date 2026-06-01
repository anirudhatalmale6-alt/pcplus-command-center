import asyncio
import httpx

TRMM_URL = "https://api.pcpluscomputing.com"
TRMM_KEY = "WDHX6IPCKJ9BISAFVOUJFFXVKKN5HMZV"
HEADERS = {"X-API-KEY": TRMM_KEY}

PCPLUS_PROCS = ["PCPlusTray.exe", "PCPlusService.exe", "PCPlusDashboard.exe"]


async def get_all_agents():
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        resp = await client.get(f"{TRMM_URL}/agents/", headers=HEADERS)
        resp.raise_for_status()
        return resp.json()


async def get_agent_processes(agent_id: str):
    async with httpx.AsyncClient(verify=False, timeout=60) as client:
        resp = await client.get(
            f"{TRMM_URL}/agents/{agent_id}/processes/", headers=HEADERS
        )
        resp.raise_for_status()
        return resp.json()


async def get_agent_detail(agent_id: str):
    async with httpx.AsyncClient(verify=False, timeout=30) as client:
        resp = await client.get(
            f"{TRMM_URL}/agents/{agent_id}/", headers=HEADERS
        )
        resp.raise_for_status()
        return resp.json()


async def benchmark_agent(agent: dict):
    agent_id = agent["agent_id"]
    hostname = agent.get("hostname", "?")

    result = {
        "hostname": hostname,
        "agent_id": agent_id,
        "status": agent.get("status", "unknown"),
        "os": agent.get("operating_system", ""),
        "cpu_model": (agent.get("cpu_model") or ["Unknown"])[0],
        "total_ram": agent.get("total_ram", 0),
        "make_model": agent.get("make_model", ""),
        "client": agent.get("client_name", ""),
        "site": agent.get("site_name", ""),
        "last_seen": agent.get("last_seen", ""),
        "logged_user": agent.get("logged_username", ""),
        "public_ip": agent.get("public_ip", ""),
        "local_ips": agent.get("local_ips", ""),
        "agent_version": agent.get("version", ""),
        "disks": [],
        "pcplus_processes": [],
        "top_processes": [],
        "total_mem_used_mb": 0,
        "total_cpu_pct": 0,
        "pcplus_mem_mb": 0,
        "pcplus_cpu_pct": 0,
        "pcplus_tray_count": 0,
        "pcplus_svc_count": 0,
        "process_count": 0,
        "issues": [],
        "error": None,
    }

    if agent.get("status") != "online":
        result["error"] = "offline"
        return result

    try:
        detail = await get_agent_detail(agent_id)
        disks = detail.get("disks") or []
        result["disks"] = [
            {
                "device": d.get("device", ""),
                "total": d.get("total", ""),
                "used": d.get("used", ""),
                "free": d.get("free", ""),
                "percent": d.get("percent", 0),
            }
            for d in disks
        ]
        result["total_ram"] = detail.get("total_ram", 0)
    except Exception:
        pass

    try:
        procs = await get_agent_processes(agent_id)
        result["process_count"] = len(procs)

        total_mem = 0
        total_cpu = 0.0
        pcplus_list = []
        others = []

        for p in procs:
            name = p.get("name", "")
            mem_bytes = p.get("membytes", 0) or 0
            cpu = float(p.get("cpu_percent", 0) or 0)
            mem_mb = round(mem_bytes / (1024 * 1024), 1)

            total_mem += mem_mb
            total_cpu += cpu

            if name in PCPLUS_PROCS:
                pcplus_list.append({
                    "name": name,
                    "pid": p.get("pid", 0),
                    "mem_mb": mem_mb,
                    "cpu_pct": cpu,
                    "user": p.get("username", ""),
                })
            elif mem_mb > 20 or cpu > 1.0:
                others.append({
                    "name": name,
                    "mem_mb": mem_mb,
                    "cpu_pct": cpu,
                })

        result["total_mem_used_mb"] = round(total_mem, 1)
        result["total_cpu_pct"] = round(total_cpu, 1)
        result["pcplus_processes"] = pcplus_list
        result["pcplus_mem_mb"] = round(
            sum(p["mem_mb"] for p in pcplus_list), 1
        )
        result["pcplus_cpu_pct"] = round(
            sum(p["cpu_pct"] for p in pcplus_list), 1
        )
        result["top_processes"] = sorted(
            others, key=lambda x: x["mem_mb"], reverse=True
        )[:15]

        tray_count = sum(1 for p in pcplus_list if "tray" in p["name"].lower())
        svc_count = sum(1 for p in pcplus_list if "service" in p["name"].lower())
        result["pcplus_tray_count"] = tray_count
        result["pcplus_svc_count"] = svc_count

        issues = []
        if tray_count > 1:
            issues.append("Duplicate Tray")
        if svc_count > 1:
            issues.append("Duplicate Service")
        if result["pcplus_mem_mb"] > 300:
            issues.append("High Memory")
        if result["pcplus_cpu_pct"] > 10:
            issues.append("High CPU")
        result["issues"] = issues

    except Exception as e:
        result["error"] = str(e)[:200]

    return result


async def get_fleet_benchmark(site_filter: str = None):
    agents = await get_all_agents()

    if site_filter:
        agents = [
            a for a in agents
            if site_filter.lower() in (a.get("site_name", "") + a.get("client_name", "")).lower()
        ]

    tasks = [benchmark_agent(a) for a in agents if a.get("status") == "online"]
    offline = [
        {
            "hostname": a.get("hostname", "?"),
            "agent_id": a.get("agent_id", ""),
            "status": a.get("status", "unknown"),
            "os": a.get("operating_system", ""),
            "cpu_model": (a.get("cpu_model") or ["Unknown"])[0],
            "total_ram": a.get("total_ram", 0),
            "make_model": a.get("make_model", ""),
            "client": a.get("client_name", ""),
            "site": a.get("site_name", ""),
            "last_seen": a.get("last_seen", ""),
            "pcplus_processes": [],
            "pcplus_mem_mb": 0,
            "pcplus_cpu_pct": 0,
            "error": "offline",
        }
        for a in agents if a.get("status") != "online"
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    online_results = []
    for r in results:
        if isinstance(r, Exception):
            continue
        online_results.append(r)

    all_results = online_results + offline
    all_results.sort(key=lambda x: x.get("hostname", "").lower())

    has_pcplus = [r for r in online_results if r.get("pcplus_mem_mb", 0) > 0]

    return {
        "agents": all_results,
        "summary": {
            "total": len(all_results),
            "online": len(online_results),
            "offline": len(offline),
            "with_pcplus": len(has_pcplus),
            "avg_pcplus_mem_mb": round(
                sum(r["pcplus_mem_mb"] for r in has_pcplus) / max(len(has_pcplus), 1), 1
            ),
            "avg_pcplus_cpu_pct": round(
                sum(r["pcplus_cpu_pct"] for r in has_pcplus) / max(len(has_pcplus), 1), 1
            ),
            "max_pcplus_mem_mb": max(
                (r["pcplus_mem_mb"] for r in has_pcplus), default=0
            ),
            "max_pcplus_cpu_mb": max(
                (r["pcplus_cpu_pct"] for r in has_pcplus), default=0
            ),
        },
    }
