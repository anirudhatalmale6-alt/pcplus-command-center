import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from modules import zammad, rmm, reminders, notifications, crashplan, calcom, threecx, meshcentral, benchmark, agent_benchmark, pc_detail, baseline


class ReminderCreate(BaseModel):
    title: str
    due_date: str | None = None
    category: str = "general"
    priority: str = "normal"


class EscalationRequest(BaseModel):
    ticket_number: str
    ticket_title: str
    minutes_waiting: int = 5


connected_clients: list[WebSocket] = []
cached_data: dict = {}


async def refresh_data():
    global cached_data
    while True:
        try:
            tickets_task = zammad.get_open_tickets()
            stats_task = zammad.get_ticket_stats()
            agents_task = rmm.get_agents_summary()
            alerts_task = rmm.get_alerts()
            backups_task = crashplan.get_backup_status()

            appointments_task = calcom.get_todays_appointments()
            missed_task = threecx.get_missed_calls()
            incoming_task = threecx.get_incoming_calls()
            active_calls_task = threecx.get_active_calls()
            mesh_task = meshcentral.get_support_sessions()
            bench_task = benchmark.get_server_benchmark()

            tickets, stats, agents, alerts, backups, appointments, missed, incoming, active_calls, mesh, bench = await asyncio.gather(
                tickets_task, stats_task, agents_task, alerts_task, backups_task,
                appointments_task, missed_task, incoming_task, active_calls_task, mesh_task, bench_task,
                return_exceptions=True
            )

            cached_data = {
                "tickets": tickets if not isinstance(tickets, Exception) else [],
                "ticket_stats": stats if not isinstance(stats, Exception) else {},
                "agents": agents if not isinstance(agents, Exception) else {},
                "alerts": alerts if not isinstance(alerts, Exception) else [],
                "backups": backups if not isinstance(backups, Exception) else {"configured": False},
                "appointments": appointments if not isinstance(appointments, Exception) else [],
                "missed_calls": missed if not isinstance(missed, Exception) else [],
                "incoming_calls": incoming if not isinstance(incoming, Exception) else [],
                "active_calls": active_calls if not isinstance(active_calls, Exception) else [],
                "remote_support": mesh if not isinstance(mesh, Exception) else {"sessions": [], "invite_url": ""},
                "benchmark": bench if not isinstance(bench, Exception) else {"server": {}, "services": {}, "other_processes": []},
                "reminders": reminders.get_reminders(),
                "updated_at": datetime.now().isoformat(),
            }

            for ws in connected_clients[:]:
                try:
                    await ws.send_json(cached_data)
                except Exception:
                    connected_clients.remove(ws)

        except Exception:
            pass

        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    reminders.carry_over_incomplete()
    task = asyncio.create_task(refresh_data())
    yield
    task.cancel()


app = FastAPI(title="PC Plus Command Center", lifespan=lifespan)


@app.get("/api/dashboard")
async def dashboard():
    if cached_data:
        return cached_data
    tickets = await zammad.get_open_tickets()
    stats = await zammad.get_ticket_stats()
    agents = await rmm.get_agents_summary()
    alerts = await rmm.get_alerts()
    backups = await crashplan.get_backup_status()
    appointments = await calcom.get_todays_appointments()
    return {
        "tickets": tickets,
        "ticket_stats": stats,
        "agents": agents,
        "alerts": alerts,
        "backups": backups,
        "appointments": appointments,
        "reminders": reminders.get_reminders(),
        "updated_at": datetime.now().isoformat(),
    }


@app.get("/api/tickets")
async def tickets():
    return await zammad.get_open_tickets()


@app.get("/api/tickets/{ticket_id}/messages")
async def ticket_messages(ticket_id: int):
    return await zammad.get_recent_articles(ticket_id)


@app.get("/api/agents")
async def agents():
    return await rmm.get_agents_summary()


@app.get("/api/alerts")
async def alerts():
    return await rmm.get_alerts()


@app.get("/api/backups")
async def backup_status():
    return await crashplan.get_backup_status()


@app.get("/api/appointments")
async def appointments():
    return await calcom.get_upcoming_appointments()


@app.get("/api/remote-support")
async def remote_support():
    return await meshcentral.get_support_sessions()


@app.get("/api/benchmark")
async def server_benchmark():
    return await benchmark.get_server_benchmark()


@app.get("/api/fleet-benchmark")
async def fleet_benchmark(site: str = None):
    return await agent_benchmark.get_fleet_benchmark(site)


@app.get("/api/agent/{agent_id}/detail")
async def agent_detail(agent_id: str):
    return await pc_detail.get_pc_detail(agent_id)


@app.post("/api/baseline/snapshot/{agent_id}")
async def take_baseline_snapshot(agent_id: str, label: str = ""):
    return await baseline.take_snapshot(agent_id, label)


@app.get("/api/baseline/list")
async def list_baselines(agent_id: str = None):
    return baseline.list_snapshots(agent_id)


@app.get("/api/baseline/snapshot/{filename}")
async def get_baseline_snapshot(filename: str):
    data = baseline.get_snapshot(filename)
    if not data:
        return JSONResponse({"error": "not found"}, status_code=404)
    return data


@app.get("/api/baseline/compare")
async def compare_baselines(a: str, b: str):
    result = baseline.compare_snapshots(a, b)
    if not result:
        return JSONResponse({"error": "snapshot not found"}, status_code=404)
    return result


@app.get("/api/reminders")
async def get_reminders():
    return reminders.get_reminders()


@app.post("/api/reminders")
async def create_reminder(r: ReminderCreate):
    return reminders.add_reminder(r.title, r.due_date, r.category, r.priority)


@app.post("/api/reminders/{reminder_id}/complete")
async def complete_reminder(reminder_id: int):
    reminders.complete_reminder(reminder_id)
    return {"status": "ok"}


@app.post("/api/escalate")
async def escalate(req: EscalationRequest):
    result = await notifications.escalate_ticket(
        req.ticket_number, req.ticket_title, req.minutes_waiting
    )
    return result


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        if cached_data:
            await websocket.send_json(cached_data)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)


app.mount("/", StaticFiles(directory="/opt/command-center/frontend", html=True), name="frontend")
