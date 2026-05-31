import httpx
from config import RMM_URL, RMM_API_KEY

HEADERS = {
    "X-API-KEY": RMM_API_KEY,
    "Content-Type": "application/json"
}


async def get_agents_summary():
    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        resp = await client.get(f"{RMM_URL}/agents/", headers=HEADERS)
        if resp.status_code != 200:
            return {"total": 0, "online": 0, "offline": 0, "agents": []}

        agents = resp.json()
        online = sum(1 for a in agents if a.get("status") == "online")
        offline = len(agents) - online

        agent_list = []
        for a in agents:
            agent_list.append({
                "hostname": a.get("hostname", ""),
                "client": a.get("client_name", a.get("site_name", "")),
                "os": a.get("operating_system", ""),
                "status": a.get("status", "unknown"),
                "last_seen": a.get("last_seen", ""),
                "cpu_model": a.get("cpu_model", [""])[0] if isinstance(a.get("cpu_model"), list) else a.get("cpu_model", ""),
                "total_ram": a.get("total_ram", 0),
            })

        return {
            "total": len(agents),
            "online": online,
            "offline": offline,
            "agents": sorted(agent_list, key=lambda x: x["status"] != "online"),
        }


async def get_alerts():
    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        resp = await client.get(f"{RMM_URL}/alerts/", headers=HEADERS)
        if resp.status_code != 200:
            return []

        alerts = resp.json()
        return [
            {
                "id": a.get("id"),
                "hostname": a.get("hostname", ""),
                "alert_type": a.get("alert_type", ""),
                "message": a.get("message", ""),
                "severity": a.get("severity", ""),
                "alert_time": a.get("alert_time", ""),
                "resolved": a.get("resolved", False),
            }
            for a in alerts[:20]
            if not a.get("resolved")
        ]
