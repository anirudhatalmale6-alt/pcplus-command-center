import json
import os
from datetime import datetime, date

DATA_FILE = "/opt/command-center/data/reminders.json"


def _load():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def _save(items):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(items, f, indent=2, default=str)


def get_reminders(include_done=False):
    items = _load()
    today = date.today().isoformat()
    results = []
    for item in items:
        if not include_done and item.get("done"):
            continue
        due = item.get("due_date", "")
        overdue = due and due < today and not item.get("done")
        results.append({**item, "overdue": overdue})
    return sorted(results, key=lambda x: (not x["overdue"], x.get("due_date", "9999")))


def add_reminder(title, due_date=None, category="general", priority="normal"):
    items = _load()
    reminder = {
        "id": len(items) + 1,
        "title": title,
        "due_date": due_date,
        "category": category,
        "priority": priority,
        "done": False,
        "created_at": datetime.now().isoformat(),
        "carried_over": 0,
    }
    items.append(reminder)
    _save(items)
    return reminder


def complete_reminder(reminder_id):
    items = _load()
    for item in items:
        if item["id"] == reminder_id:
            item["done"] = True
            item["completed_at"] = datetime.now().isoformat()
            break
    _save(items)


def carry_over_incomplete():
    items = _load()
    today = date.today().isoformat()
    for item in items:
        if not item.get("done") and item.get("due_date") and item["due_date"] < today:
            item["due_date"] = today
            item["carried_over"] = item.get("carried_over", 0) + 1
    _save(items)
    return [i for i in items if not i.get("done")]
