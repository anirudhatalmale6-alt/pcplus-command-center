import httpx
from config import ZAMMAD_URL, ZAMMAD_TOKEN
from urllib.parse import urlparse

HEADERS = {
    "Authorization": f"Token token={ZAMMAD_TOKEN}",
    "Content-Type": "application/json"
}

_parsed = urlparse(ZAMMAD_URL)
_ZAMMAD_LOCAL = f"{_parsed.scheme}://127.0.0.1"
HEADERS["Host"] = _parsed.hostname


async def get_open_tickets():
    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        resp = await client.get(
            f"{_ZAMMAD_LOCAL}/api/v1/tickets/search",
            params={
                "query": "state_id:1 OR state_id:2 OR state_id:3",
                "limit": 50,
                "expand": "true",
            },
            headers=HEADERS
        )
        if resp.status_code != 200:
            return []
        tickets = resp.json()
        if isinstance(tickets, dict):
            tickets = tickets.get("assets", {}).get("Ticket", {}).values() if "assets" in tickets else []
            tickets = list(tickets)
        if not isinstance(tickets, list):
            return []

        results = []
        for t in tickets:
            if isinstance(t, dict):
                results.append({
                    "id": t.get("id"),
                    "number": t.get("number"),
                    "title": t.get("title", ""),
                    "state": t.get("state", t.get("state_id", "")),
                    "priority": t.get("priority", t.get("priority_id", "")),
                    "customer": t.get("customer", ""),
                    "group": t.get("group", ""),
                    "created_at": t.get("created_at", ""),
                    "updated_at": t.get("updated_at", ""),
                })
        return results


async def get_ticket_stats():
    state_map = {"new": 1, "open": 2, "pending": 3}
    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        counts = {"new": 0, "open": 0, "pending": 0}
        for name, sid in state_map.items():
            resp = await client.get(
                f"{_ZAMMAD_LOCAL}/api/v1/tickets/search",
                params={"query": f"state_id:{sid}", "limit": 1},
                headers=HEADERS
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    counts[name] = len(data)
                elif isinstance(data, dict):
                    counts[name] = data.get("tickets_count", len(data.get("tickets", [])))
        return counts


async def get_recent_articles(ticket_id: int, limit: int = 3):
    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        resp = await client.get(
            f"{_ZAMMAD_LOCAL}/api/v1/ticket_articles/by_ticket/{ticket_id}",
            headers=HEADERS
        )
        if resp.status_code != 200:
            return []
        articles = resp.json()
        return [
            {
                "id": a.get("id"),
                "from": a.get("from", ""),
                "subject": a.get("subject", ""),
                "body": (a.get("body", "") or "")[:200],
                "created_at": a.get("created_at", ""),
                "type": a.get("type", ""),
            }
            for a in articles[-limit:]
        ]
