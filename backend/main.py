import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from modules import zammad, rmm, reminders, notifications


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

            tickets, stats, agents, alerts = await asyncio.gather(
                tickets_task, stats_task, agents_task, alerts_task,
                return_exceptions=True
            )

            cached_data = {
                "tickets": tickets if not isinstance(tickets, Exception) else [],
                "ticket_stats": stats if not isinstance(stats, Exception) else {},
                "agents": agents if not isinstance(agents, Exception) else {},
                "alerts": alerts if not isinstance(alerts, Exception) else [],
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
    return {
        "tickets": tickets,
        "ticket_stats": stats,
        "agents": agents,
        "alerts": alerts,
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
