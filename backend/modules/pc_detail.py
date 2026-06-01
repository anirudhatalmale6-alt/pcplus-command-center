import httpx

TRMM_URL = "https://api.pcpluscomputing.com"
TRMM_KEY = "WDHX6IPCKJ9BISAFVOUJFFXVKKN5HMZV"
HEADERS = {"X-API-KEY": TRMM_KEY}


async def _get(path: str, timeout: int = 60):
    async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
        resp = await client.get(f"{TRMM_URL}{path}", headers=HEADERS)
        resp.raise_for_status()
        return resp.json()


async def get_pc_detail(agent_id: str):
    agent = await _get(f"/agents/{agent_id}/")

    procs = []
    try:
        procs = await _get(f"/agents/{agent_id}/processes/")
    except Exception:
        pass

    software = []
    try:
        sw_data = await _get(f"/software/{agent_id}/")
        if isinstance(sw_data, dict):
            software = sw_data.get("software", [])
        elif isinstance(sw_data, list):
            software = sw_data
    except Exception:
        pass

    wmi = agent.get("wmi_detail", {}) or {}

    # Parse processes
    pcplus_procs = []
    top_by_mem = []
    top_by_cpu = []
    total_mem_mb = 0
    total_cpu = 0.0

    for p in procs:
        name = p.get("name", "")
        mem_bytes = p.get("membytes", 0) or 0
        cpu = float(p.get("cpu_percent", 0) or 0)
        mem_mb = round(mem_bytes / (1024 * 1024), 1)
        total_mem_mb += mem_mb
        total_cpu += cpu

        entry = {
            "name": name,
            "pid": p.get("pid", 0),
            "mem_mb": mem_mb,
            "cpu_pct": cpu,
            "user": p.get("username", ""),
        }

        if "pcplus" in name.lower():
            pcplus_procs.append(entry)

        if mem_mb > 5:
            top_by_mem.append(entry)
        if cpu > 0.1:
            top_by_cpu.append(entry)

    top_by_mem.sort(key=lambda x: x["mem_mb"], reverse=True)
    top_by_cpu.sort(key=lambda x: x["cpu_pct"], reverse=True)

    # Parse services
    services = agent.get("services", []) or []
    running_svcs = [s for s in services if s.get("status") == "running"]
    auto_svcs = [s for s in services if "auto" in (s.get("start_type", "")).lower()]

    # Parse WMI network
    net_adapters = []
    for group in (wmi.get("network_adapter") or []):
        if isinstance(group, list):
            for adapter in group:
                if adapter.get("NetEnabled"):
                    net_adapters.append({
                        "name": adapter.get("Name", ""),
                        "mac": adapter.get("MACAddress", ""),
                        "speed": adapter.get("Speed", ""),
                        "type": adapter.get("AdapterType", ""),
                    })

    # Parse WMI OS
    os_detail = {}
    os_data = wmi.get("os") or []
    if os_data and isinstance(os_data, list) and len(os_data) > 0:
        os_list = os_data[0] if isinstance(os_data[0], list) else os_data
        if os_list and isinstance(os_list, list) and len(os_list) > 0:
            o = os_list[0] if isinstance(os_list[0], dict) else {}
            os_detail = {
                "name": o.get("Caption", ""),
                "version": o.get("Version", ""),
                "build": o.get("BuildNumber", ""),
                "arch": o.get("OSArchitecture", ""),
                "install_date": o.get("InstallDate", ""),
                "last_boot": o.get("LastBootUpTime", ""),
                "registered_user": o.get("RegisteredUser", ""),
            }

    # Parse BIOS
    bios_info = {}
    bios_data = wmi.get("bios") or []
    if bios_data and isinstance(bios_data, list) and len(bios_data) > 0:
        bios_list = bios_data[0] if isinstance(bios_data[0], list) else bios_data
        if bios_list and isinstance(bios_list, list) and len(bios_list) > 0:
            b = bios_list[0] if isinstance(bios_list[0], dict) else {}
            bios_info = {
                "manufacturer": b.get("Manufacturer", ""),
                "version": b.get("SMBIOSBIOSVersion", ""),
                "serial": b.get("SerialNumber", ""),
            }

    # Boot time
    import datetime
    boot_ts = agent.get("boot_time", 0)
    boot_time = ""
    uptime_hours = 0
    if boot_ts:
        boot_dt = datetime.datetime.fromtimestamp(boot_ts)
        boot_time = boot_dt.isoformat()
        uptime_hours = round((datetime.datetime.now().timestamp() - boot_ts) / 3600, 1)

    return {
        "hostname": agent.get("hostname", ""),
        "agent_id": agent_id,
        "status": agent.get("status", ""),
        "operating_system": agent.get("operating_system", ""),
        "os_detail": os_detail,
        "cpu_model": (agent.get("cpu_model") or ["Unknown"])[0],
        "total_ram": agent.get("total_ram", 0),
        "make_model": agent.get("make_model", ""),
        "graphics": agent.get("graphics", ""),
        "serial_number": agent.get("serial_number", ""),
        "bios": bios_info,
        "public_ip": agent.get("public_ip", ""),
        "local_ips": agent.get("local_ips", ""),
        "logged_user": agent.get("logged_in_username", ""),
        "last_logged_user": agent.get("last_logged_in_user", ""),
        "last_seen": agent.get("last_seen", ""),
        "boot_time": boot_time,
        "uptime_hours": uptime_hours,
        "needs_reboot": agent.get("needs_reboot", False),
        "version": agent.get("version", ""),
        "site": agent.get("site_name", ""),
        "client": agent.get("client", ""),
        "disks": agent.get("disks") or [],
        "physical_disks": agent.get("physical_disks") or [],
        "network_adapters": net_adapters,
        "process_summary": {
            "total": len(procs),
            "total_mem_mb": round(total_mem_mb, 1),
            "total_cpu_pct": round(total_cpu, 1),
        },
        "pcplus_processes": pcplus_procs,
        "pcplus_total_mem_mb": round(sum(p["mem_mb"] for p in pcplus_procs), 1),
        "pcplus_total_cpu_pct": round(sum(p["cpu_pct"] for p in pcplus_procs), 1),
        "top_by_memory": top_by_mem[:30],
        "top_by_cpu": top_by_cpu[:30],
        "services_summary": {
            "total": len(services),
            "running": len(running_svcs),
            "auto_start": len(auto_svcs),
        },
        "running_services": [
            {
                "name": s.get("display_name", s.get("name", "")),
                "svc_name": s.get("name", ""),
                "start_type": s.get("start_type", ""),
                "username": s.get("username", ""),
                "pid": s.get("pid", 0),
            }
            for s in running_svcs
        ],
        "installed_software": [
            {
                "name": s.get("name", ""),
                "version": s.get("version", ""),
                "publisher": s.get("publisher", ""),
                "size": s.get("size", ""),
            }
            for s in software
        ],
        "software_count": len(software),
    }
