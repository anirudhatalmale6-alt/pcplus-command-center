import asyncpg
from datetime import datetime, timedelta, timezone

CALCOM_DB = "postgresql://calcom:01c01594bc39832f4b296259ed388e72@127.0.0.1:5432/calcom"


async def get_upcoming_appointments(days=7):
    try:
        conn = await asyncpg.connect(CALCOM_DB, timeout=10)
    except Exception:
        return []

    try:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)

        rows = await conn.fetch(
            """
            SELECT b.id, b.title, b."startTime", b."endTime", b.status,
                   b.location, b.description,
                   a.name AS attendee_name, a.email AS attendee_email
            FROM "Booking" b
            LEFT JOIN "Attendee" a ON a."bookingId" = b.id
            WHERE b."startTime" >= $1
              AND b."startTime" <= $2
              AND b.status = 'ACCEPTED'
            ORDER BY b."startTime" ASC
            LIMIT 20
            """,
            now, end,
        )

        seen = {}
        for r in rows:
            bid = r["id"]
            if bid not in seen:
                seen[bid] = {
                    "id": bid,
                    "title": r["title"] or "",
                    "start": r["startTime"].isoformat() if r["startTime"] else "",
                    "end": r["endTime"].isoformat() if r["endTime"] else "",
                    "status": r["status"] or "",
                    "location": r["location"] or "",
                    "attendees": [],
                }
            if r["attendee_name"]:
                seen[bid]["attendees"].append({
                    "name": r["attendee_name"],
                    "email": r["attendee_email"] or "",
                })

        return list(seen.values())
    except Exception:
        return []
    finally:
        await conn.close()


async def get_todays_appointments():
    try:
        conn = await asyncpg.connect(CALCOM_DB, timeout=10)
    except Exception:
        return []

    try:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        rows = await conn.fetch(
            """
            SELECT b.id, b.title, b."startTime", b."endTime", b.status,
                   b.location, a.name AS attendee_name, a.email AS attendee_email
            FROM "Booking" b
            LEFT JOIN "Attendee" a ON a."bookingId" = b.id
            WHERE b."startTime" >= $1
              AND b."startTime" < $2
              AND b.status IN ('ACCEPTED', 'PENDING')
            ORDER BY b."startTime" ASC
            """,
            start_of_day, end_of_day,
        )

        seen = {}
        for r in rows:
            bid = r["id"]
            if bid not in seen:
                seen[bid] = {
                    "id": bid,
                    "title": r["title"] or "",
                    "start": r["startTime"].isoformat() if r["startTime"] else "",
                    "end": r["endTime"].isoformat() if r["endTime"] else "",
                    "status": r["status"] or "",
                    "location": r["location"] or "",
                    "attendees": [],
                }
            if r["attendee_name"]:
                seen[bid]["attendees"].append({
                    "name": r["attendee_name"],
                    "email": r["attendee_email"] or "",
                })

        return list(seen.values())
    except Exception:
        return []
    finally:
        await conn.close()
