"""
Zeiterfassung tab: simple personal time tracking per project - a start/stop
timer in the app header (while a project is open) plus a global list to
edit entries and export them. Internal only: stored in its own global
time_entries table, never part of a project's JSON backup/duplicate or any
PDF export (Pflichtenheft, Dokumentation, ...).

Start and end times snap to the NEAREST quarter hour when saved (Start at
12:04 -> 12:00, Stop at 12:55 -> 13:00, manual entries likewise), and an
entry whose start and end snap to the same quarter still counts as 15
minutes (_snapped_range). Durations are additionally rounded UP to full 15
minutes on read, which only matters for entries saved before snapping
existed.
The PDF export (Stundennachweis) is the only export - a deliberate
exception to "never exported", since it's the user's own report, not part
of any customer documentation.
"""
import math
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table

from ..db import get_db
from ..models import TimeEntryIn, TimerStartIn
from ..pdf_design import (
    build_pdf_response, company_footer_line, company_header_block, pdf_styles, pdf_table_style,
    pdf_title_banner,
)

router = APIRouter(tags=["zeiterfassung"])

ROUND_TO_MINUTES = 15


def _snap(dt):
    """Round an aware datetime to the nearest quarter hour. Done in UTC, which
    lands on the same :00/:15/:30/:45 marks as any whole/half-hour time zone."""
    q = ROUND_TO_MINUTES * 60
    return datetime.fromtimestamp(math.floor(dt.timestamp() / q + 0.5) * q, timezone.utc)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def _snapped_range(started_at, ended_at):
    """Snapped (start, end) ISO pair; end is pushed to start + 15 min if both
    snapped onto the same quarter (a few minutes' work still counts)."""
    start, end = _snap(_parse(started_at)), _snap(_parse(ended_at))
    if end <= start:
        end = start + timedelta(minutes=ROUND_TO_MINUTES)
    return _iso(start), _iso(end)


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
            (body.project_id, _project_name(db, body.project_id), _iso(_snap(datetime.now(timezone.utc)))),
        )
        return {"id": cur.lastrowid}


@router.post("/api/time-entries/stop")
def stop_timer():
    with get_db() as db:
        running = db.execute("SELECT id, started_at FROM time_entries WHERE ended_at IS NULL").fetchall()
        for r in running:
            _, ended_at = _snapped_range(r["started_at"], _iso(datetime.now(timezone.utc)))
            db.execute("UPDATE time_entries SET ended_at=? WHERE id=?", (ended_at, r["id"]))
    return {"ok": True}


@router.post("/api/time-entries")
def add_time_entry(te: TimeEntryIn):
    """Manually add an entry (e.g. forgot to press Start)."""
    _validate_range(te.started_at, te.ended_at)
    started_at, ended_at = _snapped_range(te.started_at, te.ended_at)
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO time_entries (project_id, project_name, started_at, ended_at, note) VALUES (?, ?, ?, ?, ?)",
            (te.project_id, _project_name(db, te.project_id), started_at, ended_at, te.note),
        )
        return {"id": cur.lastrowid}


@router.put("/api/time-entries/{entry_id}")
def update_time_entry(entry_id: int, te: TimeEntryIn):
    _validate_range(te.started_at, te.ended_at)
    started_at, ended_at = _snapped_range(te.started_at, te.ended_at)
    with get_db() as db:
        db.execute(
            "UPDATE time_entries SET project_id=?, project_name=?, started_at=?, ended_at=?, note=? WHERE id=?",
            (te.project_id, _project_name(db, te.project_id), started_at, ended_at, te.note, entry_id),
        )
    return {"ok": True}


@router.delete("/api/time-entries/{entry_id}")
def delete_time_entry(entry_id: int):
    with get_db() as db:
        db.execute("DELETE FROM time_entries WHERE id=?", (entry_id,))
    return {"ok": True}


def _client_tz(tz, offset):
    """The browser's time zone for rendering times in the PDF - the server
    (container) usually runs in UTC. Prefers the IANA name (DST-correct per
    entry), falls back to the browser's current fixed UTC offset."""
    if tz:
        try:
            return ZoneInfo(tz)
        except Exception:
            pass
    return timezone(timedelta(minutes=-(offset or 0)))


def _fmt_hours(minutes):
    return f"{minutes // 60}:{minutes % 60:02d} h"


@router.get("/api/time-entries/export.pdf")
def export_time_entries_pdf(project_id: int | None = None, tz: str = "", offset: int = 0):
    """Stundennachweis: one table per project (Datum/Von/Bis/Dauer/Notiz, each
    entry rounded up to 15 min) with a per-project sum, plus a grand total when
    several projects are included. Running timers are left out."""
    zone = _client_tz(tz, offset)
    entries = [e for e in list_time_entries(project_id) if e["ended_at"]]
    entries.sort(key=lambda e: e["started_at"])
    if not entries:
        raise HTTPException(404, "Keine abgeschlossenen Zeiteinträge vorhanden")

    by_project = {}
    for e in entries:
        by_project.setdefault(e["project_name"], []).append(e)

    with get_db() as db:
        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())

    styles = pdf_styles()
    local = lambda iso: _parse(iso).astimezone(zone)
    first, last = local(entries[0]["started_at"]), local(entries[-1]["ended_at"])
    title = f"Zeiterfassung — {entries[0]['project_name']}" if project_id is not None else "Zeiterfassung — alle Projekte"
    story = company_header_block(company) + pdf_title_banner(
        title, f"Stundennachweis {first:%d.%m.%Y} – {last:%d.%m.%Y}"
    )

    cell = lambda text: Paragraph(escape(text or ""), styles["TableCell"])
    grand_total = 0
    for name in sorted(by_project, key=str.lower):
        rows = by_project[name]
        total = sum(e["billed_minutes"] for e in rows)
        grand_total += total
        table_data = [["Datum", "Von", "Bis", "Dauer", "Notiz"]]
        for e in rows:
            start, end = local(e["started_at"]), local(e["ended_at"])
            table_data.append([
                cell(f"{start:%d.%m.%Y}"), cell(f"{start:%H:%M}"), cell(f"{end:%H:%M}"),
                cell(_fmt_hours(e["billed_minutes"])), cell(e["note"]),
            ])
        table_data.append(["Summe", "", "", _fmt_hours(total), ""])
        table = Table(table_data, colWidths=[28 * mm, 18 * mm, 18 * mm, 22 * mm, 94 * mm], repeatRows=1)
        table.setStyle(pdf_table_style([
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("SPAN", (0, -1), (2, -1)),
        ]))
        story.append(KeepTogether([Paragraph(escape(name), styles["SectionHeading"]), table]))
        story.append(Spacer(1, 3 * mm))

    if len(by_project) > 1:
        story.append(Paragraph(f"Gesamt: {_fmt_hours(grand_total)}", styles["SectionHeading"]))

    file_label = entries[0]["project_name"].replace(" ", "_") if project_id is not None else "alle_Projekte"
    return build_pdf_response(
        story,
        footer_left_text="Zeiterfassung",
        filename=f"Zeiterfassung_{file_label}.pdf",
        doc_title=title,
        footer_center_text=company_footer_line(company),
    )
