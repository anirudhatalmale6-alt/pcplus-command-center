import asyncpg

MESH_DB = "postgresql://wnwolnox:EIbqCdMWmePhu3AYpWWk@127.0.0.1:5432/meshcentral"
REMOTE_SUPPORT_MESHID = "mesh//nD1fVc4Sl@cUm5UsI5fRMuvHwWEv0uL3AiydNkwhEaWH4vkeog@qznEKZGJgTd98"
MESH_URL = "https://mesh.pcpluscomputing.com"
INVITE_CODE = "pcplus2026"


async def get_support_sessions():
    try:
        conn = await asyncpg.connect(MESH_DB, timeout=10)
    except Exception:
        return {"sessions": [], "invite_url": f"{MESH_URL}/invite?inviteCode={INVITE_CODE}"}

    try:
        rows = await conn.fetch(
            """
            SELECT
              m.id,
              m.doc->>'name' as name,
              m.doc->>'rname' as real_name,
              m.doc->>'osdesc' as os,
              m.doc->>'ip' as ip,
              m.doc->'agent'->>'id' as agent_type,
              p.last_power,
              p.last_time
            FROM main m
            LEFT JOIN LATERAL (
              SELECT (doc->>'power')::int as last_power, time as last_time
              FROM power
              WHERE nodeid = m.id
              ORDER BY time DESC
              LIMIT 1
            ) p ON true
            WHERE m.type = 'node'
              AND m.doc->>'meshid' = $1
            ORDER BY p.last_power DESC NULLS LAST, p.last_time DESC NULLS LAST
            """,
            REMOTE_SUPPORT_MESHID,
        )

        sessions = []
        for r in rows:
            node_id = r["id"]
            parts = node_id.split("//", 1)
            short_id = parts[1] if len(parts) > 1 else node_id
            sessions.append({
                "id": node_id,
                "name": r["name"] or r["real_name"] or "Unknown",
                "os": r["os"] or "",
                "ip": r["ip"] or "",
                "online": r["last_power"] == 1 if r["last_power"] is not None else False,
                "last_seen": r["last_time"].isoformat() if r["last_time"] else None,
                "connect_url": f"{MESH_URL}/?node={short_id}&viewmode=11&hide=16",
            })

        return {
            "sessions": sessions,
            "invite_url": f"{MESH_URL}/invite?inviteCode={INVITE_CODE}",
        }
    except Exception:
        return {"sessions": [], "invite_url": f"{MESH_URL}/invite?inviteCode={INVITE_CODE}"}
    finally:
        await conn.close()
