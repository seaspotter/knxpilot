"""
Zeiterfassung tab: simple personal time tracking per project - a start/stop
timer in the app header (while a project is open) plus a global list to
edit entries and export them. Internal only: stored in its own global
time_entries table, never part of a project's JSON backup/duplicate or any
PDF export (Pflichtenheft, Dokumentation, ...).

Every entry's duration is rounded UP to the next full 15 minutes on read
(5 or 10 minutes worked -> 15 minutes billed); the raw start/end times are
stored unchanged so the rounding rule could change later without data loss.
"""
import math
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..models import TimeEntryIn, TimerStartIn

router = APIRouter(tags=["zeiterfassung"])

ROUND_TO_MINUTES = 15


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse(value):
    """ISO string -> aware UTC datetime (naive input is treated as UTC)."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        raise HTTPException(400, f"Ungültige Zeitangabe: {value}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _billed_minutes(raw_minutes):
    return math.ceil(raw_minutes / ROUND_TO_MINUTES) * ROUND_TO_MINUTES if raw_minutes > 0 else 0


def _entry_dict(r):
    raw_minutes = 0.0
    if r["ended_at"]:
        raw_minutes = max(0.0, (_parse(r["ended_at"]) - _parse(r["started_at"])).total_seconds() / 60)
    return {
        "id": r["id"], "project_id": r["project_id"],
        # Current project name if the project still exists, else the snapshot.
        "project_name": r["current_name"] or r["project_name"],
        "started_at": r["started_at"], "ended_at": r["ended_at"], "note": r["note"],
        "raw_minutes": round(raw_minutes, 1),
        "billed_minutes": _billed_minutes(raw_minutes),
    }


_SELECT = (
    "SELECT te.*, p.name AS current_name FROM time_entries te "
    "LEFT JOIN projects p ON te.project_id = p.id"
)


def _project_name(db, project_id):
    row = db.execute("SELECT name FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Projekt nicht gefunden")
    return row["name"]


def _validate_range(started_at, ended_at):
    if _parse(ended_at) < _parse(started_at):
        raise HTTPException(400, "Ende liegt vor dem Start")


@router.get("/api/time-entries")
def list_time_entries(project_id: int | None = None):
    with get_db() as db:
        if project_id is None:
            rows = db.execute(f"{_SELECT} ORDER BY te.started_at DESC").fetchall()
        else:
            rows = db.execute(
                f"{_SELECT} WHERE te.project_id=? ORDER BY te.started_at DESC", (project_id,)
            ).fetchall()
        return [_entry_dict(r) for r in rows]


@router.get("/api/time-entries/running")
def get_running_timer():
    with get_db() as db:
        row = db.execute(f"{_SELECT} WHERE te.ended_at IS NULL ORDER BY te.id DESC LIMIT 1").fetchone()
        return _entry_dict(row) if row else None


@router.post("/api/time-entries/start")
def start_timer(body: TimerStartIn):
    with get_db() as db:
        running = db.execute(f"{_SELECT} WHERE te.ended_at IS NULL").fetchone()
        if running:
            name = running["current_name"] or running["project_name"]
            raise HTTPException(409, f"Es läuft bereits eine Zeiterfassung für \"{name}\" - bitte zuerst stoppen.")
        cur = db.execute(
            "INSERT INTO time_entries (project_id, project_name, started_at) VALUES (?, ?, ?)",
            (body.project_id, _project_name(db, body.project_id), _now_iso()),
        )
        return {"id": cur.lastrowid}


@router.post("/api/time-entries/stop")
def stop_timer():
    with get_db() as db:
        db.execute("UPDATE time_entries SET ended_at=? WHERE ended_at IS NULL", (_now_iso(),))
    return {"ok": True}


@router.post("/api/time-entries")
def add_time_entry(te: TimeEntryIn):
    """Manually add an entry (e.g. forgot to press Start)."""
    _validate_range(te.started_at, te.ended_at)
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO time_entries (project_id, project_name, started_at, ended_at, note) VALUES (?, ?, ?, ?, ?)",
            (te.project_id, _project_name(db, te.project_id),
             _parse(te.started_at).isoformat(timespec="seconds"),
             _parse(te.ended_at).isoformat(timespec="seconds"), te.note),
        )
        return {"id": cur.lastrowid}


@router.put("/api/time-entries/{entry_id}")
def update_time_entry(entry_id: int, te: TimeEntryIn):
    _validate_range(te.started_at, te.ended_at)
    with get_db() as db:
        db.execute(
            "UPDATE time_entries SET project_id=?, project_name=?, started_at=?, ended_at=?, note=? WHERE id=?",
            (te.project_id, _project_name(db, te.project_id),
             _parse(te.started_at).isoformat(timespec="seconds"),
             _parse(te.ended_at).isoformat(timespec="seconds"), te.note, entry_id),
        )
    return {"ok": True}


@router.delete("/api/time-entries/{entry_id}")
def delete_time_entry(entry_id: int):
    with get_db() as db:
        db.execute("DELETE FROM time_entries WHERE id=?", (entry_id,))
    return {"ok": True}
