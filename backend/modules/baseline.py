import asyncio
import json
import os
from datetime import datetime

import httpx

TRMM_URL = "https://api.pcpluscomputing.com"
TRMM_KEY = "WDHX6IPCKJ9BISAFVOUJFFXVKKN5HMZV"
HEADERS = {"X-API-KEY": TRMM_KEY}

BASELINE_DIR = "/opt/command-center/baselines"
os.makedirs(BASELINE_DIR, exist_ok=True)


async def _get(path: str, timeout: int = 60):
    async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
        resp = await client.get(f"{TRMM_URL}{path}", headers=HEADERS)
        resp.raise_for_status()
        return resp.json()


async def take_snapshot(agent_id: str, label: str = ""):
    agent = await _get(f"/agents/{agent_id}/")
    hostname = agent.get("hostname", "unknown")

    procs = []
    try:
        procs = await _get(f"/agents/{agent_id}/processes/")
    except Exception:
        pass

    total_mem = 0
    total_cpu = 0.0
    pcplus_procs = []
    all_procs = []

    for p in procs:
        name = p.get("name", "")
        mem_bytes = p.get("membytes", 0) or 0
        cpu = float(p.get("cpu_percent", 0) or 0)
        mem_mb = round(mem_bytes / (1024 * 1024), 1)
        total_mem += mem_mb
        total_cpu += cpu

        entry = {
            "name": name,
            "pid": p.get("pid", 0),
            "mem_mb": mem_mb,
            "cpu_pct": cpu,
            "user": p.get("username", ""),
        }

        if "pcplus" in name.lower():
            pcplus_procs.append(entry)

        if mem_mb > 5 or cpu > 0.5:
            all_procs.append(entry)

    all_procs.sort(key=lambda x: x["mem_mb"], reverse=True)

    snapshot = {
        "agent_id": agent_id,
        "hostname": hostname,
        "label": label,
        "timestamp": datetime.now().isoformat(),
        "status": agent.get("status", ""),
        "total_ram_gb": agent.get("total_ram", 0),
        "process_count": len(procs),
        "total_mem_mb": round(total_mem, 1),
        "total_cpu_pct": round(total_cpu, 1),
        "pcplus_processes": pcplus_procs,
        "pcplus_mem_mb": round(sum(p["mem_mb"] for p in pcplus_procs), 1),
        "pcplus_cpu_pct": round(sum(p["cpu_pct"] for p in pcplus_procs), 1),
        "pcplus_count": len(pcplus_procs),
        "top_processes": all_procs[:30],
        "disks": agent.get("disks") or [],
    }

    fname = f"{hostname}_{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    fpath = os.path.join(BASELINE_DIR, fname)
    with open(fpath, "w") as f:
        json.dump(snapshot, f, indent=2)

    return snapshot


def list_snapshots(agent_id: str = None):
    results = []
    for fname in os.listdir(BASELINE_DIR):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(BASELINE_DIR, fname)
        try:
            with open(fpath) as f:
                data = json.load(f)
            if agent_id and data.get("agent_id") != agent_id:
                continue
            results.append({
                "file": fname,
                "hostname": data.get("hostname", ""),
                "agent_id": data.get("agent_id", ""),
                "label": data.get("label", ""),
                "timestamp": data.get("timestamp", ""),
                "total_mem_mb": data.get("total_mem_mb", 0),
                "total_cpu_pct": data.get("total_cpu_pct", 0),
                "pcplus_mem_mb": data.get("pcplus_mem_mb", 0),
                "pcplus_cpu_pct": data.get("pcplus_cpu_pct", 0),
                "pcplus_count": data.get("pcplus_count", 0),
                "process_count": data.get("process_count", 0),
            })
        except Exception:
            continue
    results.sort(key=lambda x: x["timestamp"], reverse=True)
    return results


def get_snapshot(filename: str):
    fpath = os.path.join(BASELINE_DIR, filename)
    if not os.path.exists(fpath):
        return None
    with open(fpath) as f:
        return json.load(f)


def compare_snapshots(file_a: str, file_b: str):
    a = get_snapshot(file_a)
    b = get_snapshot(file_b)
    if not a or not b:
        return None

    def delta(key):
        va = a.get(key, 0)
        vb = b.get(key, 0)
        return {"before": va, "after": vb, "delta": round(vb - va, 1)}

    a_proc_map = {p["name"]: p for p in a.get("top_processes", [])}
    b_proc_map = {p["name"]: p for p in b.get("top_processes", [])}
    all_names = set(list(a_proc_map.keys()) + list(b_proc_map.keys()))

    proc_changes = []
    for name in all_names:
        pa = a_proc_map.get(name, {"mem_mb": 0, "cpu_pct": 0})
        pb = b_proc_map.get(name, {"mem_mb": 0, "cpu_pct": 0})
        mem_delta = round(pb["mem_mb"] - pa["mem_mb"], 1)
        cpu_delta = round(pb["cpu_pct"] - pa["cpu_pct"], 1)
        if abs(mem_delta) > 1 or abs(cpu_delta) > 0.5:
            proc_changes.append({
                "name": name,
                "mem_before": pa["mem_mb"],
                "mem_after": pb["mem_mb"],
                "mem_delta": mem_delta,
                "cpu_before": pa["cpu_pct"],
                "cpu_after": pb["cpu_pct"],
                "cpu_delta": cpu_delta,
            })

    proc_changes.sort(key=lambda x: abs(x["mem_delta"]), reverse=True)

    return {
        "before": {
            "file": file_a,
            "hostname": a.get("hostname"),
            "label": a.get("label"),
            "timestamp": a.get("timestamp"),
        },
        "after": {
            "file": file_b,
            "hostname": b.get("hostname"),
            "label": b.get("label"),
            "timestamp": b.get("timestamp"),
        },
        "summary": {
            "total_mem_mb": delta("total_mem_mb"),
            "total_cpu_pct": delta("total_cpu_pct"),
            "pcplus_mem_mb": delta("pcplus_mem_mb"),
            "pcplus_cpu_pct": delta("pcplus_cpu_pct"),
            "pcplus_count": delta("pcplus_count"),
            "process_count": delta("process_count"),
        },
        "process_changes": proc_changes[:40],
    }
