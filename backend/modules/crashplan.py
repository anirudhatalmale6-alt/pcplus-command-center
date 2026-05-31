import httpx
import time
from datetime import datetime, timezone
from config import CRASHPLAN_BASE_URL, CRASHPLAN_CLIENT_ID, CRASHPLAN_CLIENT_SECRET

_token = None
_token_expires = 0

STALE_DAYS_WARN = 7
STALE_DAYS_CRIT = 30


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


def _days_since(date_str):
    if not date_str:
        return 9999
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 9999


def _format_bytes(b):
    b = int(b or 0)
    if b >= 1024**3:
        return f"{b / 1024**3:.1f} GB"
    if b >= 1024**2:
        return f"{b / 1024**2:.0f} MB"
    return f"{b / 1024:.0f} KB"


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
        raw_devices = data.get("data", [])
        if not isinstance(raw_devices, list):
            raw_devices = []

        devices = []
        ok_count = 0
        warn_count = 0
        critical_count = 0

        for d in raw_devices:
            if not isinstance(d, dict):
                continue

            name = d.get("deviceName", d.get("deviceOsHostname", "Unknown"))
            alert_state = d.get("alertStates", "OK")
            pct_str = d.get("backupCompletePercentage", "0")
            pct = float(pct_str) if pct_str else 0
            last_backup = d.get("lastCompletedBackupDate", "")
            last_connected = d.get("lastConnectedDate", "")
            selected = d.get("selectedBytes", "0")
            archived = d.get("archiveBytes", "0")
            os_name = d.get("os", "")
            user = d.get("username", d.get("email", ""))
            cold = d.get("coldStorage", "false") == "true"
            version = d.get("version", "")

            days_stale = _days_since(last_backup)

            if alert_state not in ("OK", "") or cold or days_stale >= STALE_DAYS_CRIT:
                health = "critical"
                critical_count += 1
            elif days_stale >= STALE_DAYS_WARN or pct < 99:
                health = "warning"
                warn_count += 1
            else:
                health = "ok"
                ok_count += 1

            status_text = "OK"
            if days_stale >= STALE_DAYS_CRIT:
                status_text = f"No backup in {days_stale}d"
            elif days_stale >= STALE_DAYS_WARN:
                status_text = f"Stale ({days_stale}d ago)"
            elif cold:
                status_text = "Cold Storage"
            elif pct < 100:
                status_text = f"Backing up ({pct:.0f}%)"
            elif alert_state != "OK":
                status_text = alert_state

            devices.append({
                "name": name,
                "health": health,
                "status": status_text,
                "alert_state": alert_state,
                "percent": pct,
                "last_backup": last_backup,
                "last_connected": last_connected,
                "selected_size": _format_bytes(selected),
                "archive_size": _format_bytes(archived),
                "os": os_name,
                "user": user,
                "version": version,
            })

        devices.sort(key=lambda x: ({"critical": 0, "warning": 1, "ok": 2}.get(x["health"], 3)))

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
