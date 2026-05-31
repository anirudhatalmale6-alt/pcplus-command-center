import httpx
import re
import time
from datetime import datetime, timedelta, timezone
from config import THREECX_URL, THREECX_USER, THREECX_PASS

_token = None
_token_expires = 0


async def _get_token():
    global _token, _token_expires
    if _token and time.time() < _token_expires - 60:
        return _token
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{THREECX_URL}/webclient/api/Login/GetAccessToken",
            json={"Username": THREECX_USER, "Password": THREECX_PASS},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("Status") != "AuthSuccess":
            return None
        token_data = data.get("Token", {})
        _token = token_data.get("access_token")
        _token_expires = time.time() + token_data.get("expires_in", 3600)
        return _token


def _parse_duration(iso_dur):
    if not iso_dur or iso_dur == "PT0S":
        return 0
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", iso_dur)
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mi = int(m.group(2) or 0)
    s = float(m.group(3) or 0)
    return int(h * 3600 + mi * 60 + s)


def _format_duration(secs):
    if secs < 60:
        return f"{secs}s"
    m, s = divmod(secs, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def _seven_days_ago():
    return (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")


async def get_missed_calls(limit=15):
    token = await _get_token()
    if not token:
        return []

    headers = {"Authorization": f"Bearer {token}"}
    cutoff = _seven_days_ago()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{THREECX_URL}/xapi/v1/CallHistoryView",
            params={
                "$filter": f"CallAnswered eq false and SrcExternal eq true and DstDn ne 'EndCall' and SegmentStartTime ge {cutoff}",
                "$top": str(limit),
                "$orderby": "SegmentStartTime desc",
            },
            headers=headers,
        )
        if resp.status_code != 200:
            return []

        calls = resp.json().get("value", [])

        seen = {}
        results = []
        for c in calls:
            caller = c.get("SrcCallerNumber", "")
            ts = c.get("SegmentStartTime", "")
            key = f"{caller}_{ts[:16]}"
            if key in seen:
                continue
            seen[key] = True

            results.append({
                "caller_name": c.get("SrcDisplayName", ""),
                "caller_number": caller,
                "time": ts,
                "destination": c.get("DstDisplayName", ""),
            })
        return results


async def get_incoming_calls(limit=20):
    token = await _get_token()
    if not token:
        return []

    headers = {"Authorization": f"Bearer {token}"}
    cutoff = _seven_days_ago()

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{THREECX_URL}/xapi/v1/CallHistoryView",
            params={
                "$filter": f"CallAnswered eq true and SrcExternal eq true and DstInternal eq true and SegmentStartTime ge {cutoff}",
                "$top": str(limit),
                "$orderby": "SegmentStartTime desc",
            },
            headers=headers,
        )
        if resp.status_code != 200:
            return []

        calls = resp.json().get("value", [])

        results = []
        for c in calls:
            dur_secs = _parse_duration(c.get("CallTime", ""))
            if dur_secs == 0:
                continue

            results.append({
                "caller_name": c.get("SrcDisplayName", ""),
                "caller_number": c.get("SrcCallerNumber", ""),
                "answered_by": c.get("DstDisplayName", ""),
                "extension": c.get("DstDn", ""),
                "time": c.get("SegmentStartTime", ""),
                "duration": _format_duration(dur_secs),
                "duration_secs": dur_secs,
            })
        return results


async def get_active_calls():
    token = await _get_token()
    if not token:
        return []

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{THREECX_URL}/xapi/v1/ActiveCalls",
            headers=headers,
        )
        if resp.status_code != 200:
            return []

        return [
            {
                "caller": c.get("Caller", ""),
                "callee": c.get("Callee", ""),
                "status": c.get("Status", ""),
                "started": c.get("EstablishedAt", ""),
            }
            for c in resp.json().get("value", [])
        ]
