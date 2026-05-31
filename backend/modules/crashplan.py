import httpx
import time
from config import CRASHPLAN_BASE_URL, CRASHPLAN_CLIENT_ID, CRASHPLAN_CLIENT_SECRET

_token = None
_token_expires = 0


async def _get_token():
    global _token, _token_expires
    if _token and time.time() < _token_expires - 30:
        return _token
    if not CRASHPLAN_CLIENT_SECRET:
        return None
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{CRASHPLAN_BASE_URL}/api/v3/oauth/token",
            params={"grant_type": "client_credentials"},
            auth=(CRASHPLAN_CLIENT_ID, CRASHPLAN_CLIENT_SECRET),
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        _token = data["access_token"]
        _token_expires = time.time() + data.get("expires_in", 900)
        return _token


async def get_backup_status():
    token = await _get_token()
    if not token:
        return {"configured": False, "devices": [], "summary": {}}

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{CRASHPLAN_BASE_URL}/api/DeviceBackupReport",
            params={"active": "true", "srtKey": "lastConnectedDate", "srtDir": "desc"},
            headers=headers,
        )
        if resp.status_code != 200:
            return {"configured": True, "error": f"API returned {resp.status_code}", "devices": [], "summary": {}}

        data = resp.json()
        raw_devices = data.get("data", data) if isinstance(data, dict) else data
        if isinstance(raw_devices, dict):
            raw_devices = raw_devices.get("computers", raw_devices.get("data", []))
        if not isinstance(raw_devices, list):
            raw_devices = []

        devices = []
        ok_count = 0
        warn_count = 0
        critical_count = 0

        for d in raw_devices:
            if not isinstance(d, dict):
                continue

            name = d.get("name", d.get("computerName", d.get("hostname", "Unknown")))
            status = d.get("status", d.get("backupStatus", "unknown")).lower()
            last_backup = d.get("lastBackup", d.get("lastCompletedBackup", d.get("lastConnectedDate", "")))
            pct = d.get("percentComplete", d.get("backupPercentComplete", None))
            alert = d.get("alertState", d.get("alerted", False))
            os_name = d.get("osName", d.get("os", ""))
            user = d.get("userName", d.get("userEmail", d.get("user", "")))

            if alert or "critical" in status or "error" in status:
                health = "critical"
                critical_count += 1
            elif "warn" in status or "late" in status or pct is not None and pct < 100:
                health = "warning"
                warn_count += 1
            else:
                health = "ok"
                ok_count += 1

            devices.append({
                "name": name,
                "status": status,
                "health": health,
                "last_backup": last_backup,
                "percent_complete": pct,
                "os": os_name,
                "user": user,
                "alerted": bool(alert),
            })

        return {
            "configured": True,
            "devices": devices,
            "summary": {
                "total": len(devices),
                "ok": ok_count,
                "warning": warn_count,
                "critical": critical_count,
            },
        }
