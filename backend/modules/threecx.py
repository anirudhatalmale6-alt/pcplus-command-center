import httpx
import time
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


async def get_missed_calls(limit=15):
    token = await _get_token()
    if not token:
        return []

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{THREECX_URL}/xapi/v1/CallHistoryView",
            params={
                "$filter": "CallAnswered eq false and SrcExternal eq true and DstDn ne 'EndCall'",
                "$top": str(limit),
                "$orderby": "SegmentStartTime desc",
            },
            headers=headers,
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        calls = data.get("value", [])

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

        data = resp.json()
        return [
            {
                "caller": c.get("Caller", ""),
                "callee": c.get("Callee", ""),
                "status": c.get("Status", ""),
                "started": c.get("EstablishedAt", ""),
            }
            for c in data.get("value", [])
        ]
