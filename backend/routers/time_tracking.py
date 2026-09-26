"""
Time tracking tab ("Zeiterfassung"): simple personal time tracking per project - a start/stop
timer in the app header (while a project is open) plus a global list to
edit entries and export them. Internal only: stored in its own global
time_entries table, never part of a project's JSON backup/duplicate or any
PDF export (Pflichtenheft, Dokumentation, ...).

Start and end times snap to the NEAREST mark of the configured grid when
saved (Setup -> Zeiterfassung: 1 = minutengenau, 15 or 30 min; with 15:
Start at 12:04 -> 12:00, Stop at 12:55 -> 13:00, manual entries likewise),
and an entry whose start and end snap onto the same mark still counts as
one grid step (_snapped_range). The stored times are the source of truth:
changing the grid later never recalculates already-saved entries, so an
already-invoiced total can't shift. The whole feature can be switched off
there too (tab + header timer hidden, data kept).
The PDF export (Stundennachweis) is the only export - a deliberate
exception to "never exported", since it's the user's own report, not part
of any customer documentation.

The tab itself is rendered server-side with htmx (templates in
backend/templates/time_tracking/, /hx/... endpoints at the end of this
file, times shown in the browser's zone via templating.client_zone). The
JSON endpoints stay for the header timer (time_tracking.js), the PDF
export and the tests.
"""
import math
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import json

from fastapi import APIRouter, Form, HTTPException, Request, Response
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table

from ..db import get_db
from ..models import TimeEntriesInvoicedIn, TimeEntryIn, TimerStartIn
from ..templating import client_zone, templates
from ..pdf_design import (
    build_pdf_response, company_footer_line, company_header_block, pdf_styles, pdf_table_style,
    pdf_title_banner,
)

router = APIRouter(tags=["time-tracking"])

def _settings(db):
    r = db.execute(
        "SELECT time_tracking_enabled, time_tracking_rounding_minutes FROM company_profile WHERE id=1"
    ).fetchone()
    return bool(r["time_tracking_enabled"]), r["time_tracking_rounding_minutes"] or 1


def _snap(dt, minutes):
    """Round an aware datetime to the nearest `minutes` mark. Done in UTC, which
    lands on the same :00/:15/:30/:45 marks as any whole/half-hour time zone."""
    q = minutes * 60
    return datetime.fromtimestamp(math.floor(dt.timestamp() / q + 0.5) * q, timezone.utc)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def _snapped_range(started_at, ended_at, minutes):
    """Snapped (start, end) ISO pair; end is pushed one grid step past start if
    both snapped onto the same mark (a few minutes' work still counts)."""
    start, end = _snap(_parse(started_at), minutes), _snap(_parse(ended_at), minutes)
    if end <= start:
        end = start + timedelta(minutes=minutes)
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
    """Whole minutes, rounded up - the grid rounding already happened on save."""
    return math.ceil(round(raw_minutes, 6)) if raw_minutes > 0 else 0


def _entry_dict(r):
    raw_minutes = 0.0
    if r["ended_at"]:
        raw_minutes = max(0.0, (_parse(r["ended_at"]) - _parse(r["started_at"])).total_seconds() / 60)
    return {
        "id": r["id"], "project_id": r["project_id"],
        # Current project name if the project still exists, else the snapshot.
        "project_name": r["current_name"] or r["project_name"],
        "started_at": r["started_at"], "ended_at": r["ended_at"], "note": r["note"],
        "invoiced": bool(r["invoiced"]),
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
def list_time_entries(project_id: int | None = None, invoiced: bool | None = None):
    where, params = [], []
    if project_id is not None:
        where.append("te.project_id=?")
        params.append(project_id)
    if invoiced is not None:
        where.append("te.invoiced=?")
        params.append(int(invoiced))
    clause = f" WHERE {' AND '.join(where)}" if where else ""
    with get_db() as db:
        rows = db.execute(f"{_SELECT}{clause} ORDER BY te.started_at DESC", params).fetchall()
        return [_entry_dict(r) for r in rows]


@router.put("/api/time-entries/invoiced")
def set_time_entries_invoiced(body: TimeEntriesInvoicedIn):
    """Set/clear the "abgerechnet" flag on one or several entries at once
    (single checkbox, or "Alle angezeigten als abgerechnet markieren")."""
    with get_db() as db:
        db.executemany(
            "UPDATE time_entries SET invoiced=? WHERE id=?", [(int(body.invoiced), i) for i in body.ids]
        )
    return {"ok": True}


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
        enabled, minutes = _settings(db)
        if not enabled:
            raise HTTPException(400, "Zeiterfassung ist deaktiviert (Setup → Zeiterfassung)")
        cur = db.execute(
            "INSERT INTO time_entries (project_id, project_name, started_at) VALUES (?, ?, ?)",
            (body.project_id, _project_name(db, body.project_id), _iso(_snap(datetime.now(timezone.utc), minutes))),
        )
        return {"id": cur.lastrowid}


@router.post("/api/time-entries/stop")
def stop_timer():
    with get_db() as db:
        _, minutes = _settings(db)
        running = db.execute("SELECT id, started_at FROM time_entries WHERE ended_at IS NULL").fetchall()
        for r in running:
            _, ended_at = _snapped_range(r["started_at"], _iso(datetime.now(timezone.utc)), minutes)
            db.execute("UPDATE time_entries SET ended_at=? WHERE id=?", (ended_at, r["id"]))
    return {"ok": True}


@router.post("/api/time-entries")
def add_time_entry(te: TimeEntryIn):
    """Manually add an entry (e.g. forgot to press Start)."""
    _validate_range(te.started_at, te.ended_at)
    with get_db() as db:
        started_at, ended_at = _snapped_range(te.started_at, te.ended_at, _settings(db)[1])
        cur = db.execute(
            "INSERT INTO time_entries (project_id, project_name, started_at, ended_at, note) VALUES (?, ?, ?, ?, ?)",
            (te.project_id, _project_name(db, te.project_id), started_at, ended_at, te.note),
        )
        return {"id": cur.lastrowid}


@router.put("/api/time-entries/{entry_id}")
def update_time_entry(entry_id: int, te: TimeEntryIn):
    """Unchanged times are kept exactly as stored (never re-snapped to the
    current grid - e.g. fixing only the note on an entry saved under an older
    rounding setting must not shift its already-invoiced duration); only
    times that actually changed get snapped. Likewise an entry of a since-
    deleted project can be saved while keeping that project (its stored
    name snapshot), instead of forcing a move to some other project."""
    _validate_range(te.started_at, te.ended_at)
    with get_db() as db:
        row = db.execute("SELECT * FROM time_entries WHERE id=?", (entry_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Eintrag nicht gefunden")
        unchanged = (
            row["ended_at"] is not None
            and _parse(te.started_at) == _parse(row["started_at"])
            and _parse(te.ended_at) == _parse(row["ended_at"])
        )
        if unchanged:
            started_at, ended_at = row["started_at"], row["ended_at"]
        else:
            started_at, ended_at = _snapped_range(te.started_at, te.ended_at, _settings(db)[1])
        project_exists = db.execute("SELECT 1 FROM projects WHERE id=?", (te.project_id,)).fetchone()
        if te.project_id == row["project_id"] and not project_exists:
            project_name = row["project_name"]
        else:
            project_name = _project_name(db, te.project_id)
        db.execute(
            "UPDATE time_entries SET project_id=?, project_name=?, started_at=?, ended_at=?, note=? WHERE id=?",
            (te.project_id, project_name, started_at, ended_at, te.note, entry_id),
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
def export_time_entries_pdf(
    project_id: int | None = None, invoiced: bool | None = None, tz: str = "", offset: int = 0
):
    """Stundennachweis: one table per project (Datum/Von/Bis/Dauer/Notiz)
    with a per-project sum, plus a grand total when several projects are included. Running timers are left out. Follows the
    tab's filters (project, abgerechnet yes/no)."""
    zone = _client_tz(tz, offset)
    entries = [e for e in list_time_entries(project_id, invoiced) if e["ended_at"]]
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


# ---------- htmx fragments (backend/templates/time_tracking/) ----------
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _bool_or_none(value):
    return None if value in (None, "") else value in ("1", "true", "True")


def _int_or_none(value):
    return int(value) if value not in (None, "") else None


def _view_entries(entries, zone):
    """Entries with their times as local date/time strings for the table."""
    out = []
    for e in entries:
        start = _parse(e["started_at"]).astimezone(zone)
        end = _parse(e["ended_at"]).astimezone(zone) if e["ended_at"] else None
        out.append({**e, "date": f"{WEEKDAYS[start.weekday()]}., {start:%d.%m.%Y}", "start": f"{start:%H:%M}",
                    "end": f"{end:%H:%M}" if end else None, "hours": _fmt_hours(e["billed_minutes"])})
    return out


def _list_context(project_id, invoiced, zone):
    all_entries = list_time_entries()
    entries = [e for e in all_entries
               if (project_id is None or e["project_id"] == project_id)
               and (invoiced is None or e["invoiced"] == invoiced)]
    done = [e for e in entries if e["ended_at"]]
    totals = {}
    if project_id is None:
        for e in done:
            t = totals.setdefault(e["project_id"], {"name": e["project_name"], "minutes": 0})
            t["minutes"] += e["billed_minutes"]
    return {
        "entries": _view_entries(entries, zone), "any_entries": bool(all_entries),
        "total": _fmt_hours(sum(e["billed_minutes"] for e in done)) if done else "",
        "totals": [{"name": t["name"], "hours": _fmt_hours(t["minutes"])}
                   for t in sorted(totals.values(), key=lambda t: t["name"].lower())],
        "uninvoiced_count": sum(not e["invoiced"] for e in done),
    }


def _changed(extra=None):
    """Mutations answer with no body; the list re-fetches itself on this event
    (hx-trigger="time-entries-changed from:body" in tab.html)."""
    response = Response(status_code=200)
    response.headers["HX-Trigger"] = json.dumps({"time-entries-changed": True, **(extra or {})})
    return response


@router.get("/hx/time-tracking")
def hx_tab(request: Request, project_id: str = "", invoiced: str = ""):
    with get_db() as db:
        _, minutes = _settings(db)
        projects = {r["id"]: r["name"] for r in db.execute("SELECT id, name FROM projects").fetchall()}
    for e in list_time_entries():   # entries of since-deleted projects stay filterable
        projects.setdefault(e["project_id"], e["project_name"])
    pid, inv = _int_or_none(project_id), _bool_or_none(invoiced)
    return templates.TemplateResponse(request, "time_tracking/tab.html", {
        "minutes": minutes, "project_id": pid, "invoiced": invoiced,
        "projects": sorted(projects.items(), key=lambda p: p[1].lower()),
        **_list_context(pid, inv, client_zone(request)),
    })


@router.get("/hx/time-tracking/list")
def hx_list(request: Request, project_id: str = "", invoiced: str = ""):
    return templates.TemplateResponse(request, "time_tracking/_list.html",
                                      _list_context(_int_or_none(project_id), _bool_or_none(invoiced), client_zone(request)))


@router.post("/hx/time-tracking/entries/{entry_id}/invoiced")
def hx_set_invoiced(entry_id: int, invoiced: str = Form(...)):
    set_time_entries_invoiced(TimeEntriesInvoicedIn(ids=[entry_id], invoiced=invoiced == "true"))
    return _changed()


@router.post("/hx/time-tracking/mark-invoiced")
def hx_mark_shown_invoiced(project_id: str = Form(""), invoiced: str = Form("")):
    """"Alle angezeigten als abgerechnet markieren" - the finished, not yet
    invoiced entries of the current filter."""
    pid, inv = _int_or_none(project_id), _bool_or_none(invoiced)
    ids = [e["id"] for e in list_time_entries(pid, inv) if e["ended_at"] and not e["invoiced"]]
    set_time_entries_invoiced(TimeEntriesInvoicedIn(ids=ids, invoiced=True))
    return _changed()


@router.delete("/hx/time-tracking/entries/{entry_id}")
def hx_delete(entry_id: int):
    delete_time_entry(entry_id)
    return _changed()


def _local_parts(iso, zone, minutes=1):
    """Stored UTC time -> (date, "HH:MM") in the browser's zone, snapped to
    the grid (minutes=1: exact, for showing an existing entry as stored)."""
    dt = _snap(_parse(iso), minutes).astimezone(zone)
    return f"{dt:%Y-%m-%d}", f"{dt:%H:%M}"


def _grid_times(minutes, extra=()):
    times = [f"{m // 60:02d}:{m % 60:02d}" for m in range(0, 1440, minutes)]
    return sorted(set(times) | {t for t in extra if t})


@router.get("/hx/time-tracking/entries/new")
def hx_new_form(request: Request, current_project: str = "", project_id: str = ""):
    """"Eintrag nachtragen": last hour, on the grid, for the open project (or the filtered one)."""
    zone = client_zone(request)
    with get_db() as db:
        _, minutes = _settings(db)
        projects = [dict(r) for r in db.execute("SELECT id, name FROM projects ORDER BY name COLLATE NOCASE").fetchall()]
    now = datetime.now(timezone.utc)
    date, start = _local_parts(_iso(now - timedelta(hours=1)), zone, minutes)
    _, end = _local_parts(_iso(now), zone, minutes)
    selected = _int_or_none(current_project) or _int_or_none(project_id) or (projects[0]["id"] if projects else None)
    return templates.TemplateResponse(request, "time_tracking/_entry_form.html", {
        "entry": None, "projects": projects, "selected": selected, "date": date, "start": start, "end": end,
        "note": "", "minutes": minutes, "times": _grid_times(minutes)})


@router.get("/hx/time-tracking/entries/{entry_id}/edit")
def hx_edit_form(request: Request, entry_id: int):
    zone = client_zone(request)
    entry = next((e for e in list_time_entries() if e["id"] == entry_id), None)
    if not entry or not entry["ended_at"]:
        raise HTTPException(404, "Eintrag nicht gefunden")
    with get_db() as db:
        _, minutes = _settings(db)
        projects = [dict(r) for r in db.execute("SELECT id, name FROM projects ORDER BY name COLLATE NOCASE").fetchall()]
    if not any(p["id"] == entry["project_id"] for p in projects):   # since-deleted project stays selectable
        projects.append({"id": entry["project_id"], "name": f"{entry['project_name']} (gelöscht)"})
    date, start = _local_parts(entry["started_at"], zone)
    _, end = _local_parts(entry["ended_at"], zone)
    return templates.TemplateResponse(request, "time_tracking/_entry_form.html", {
        "entry": entry, "projects": projects, "selected": entry["project_id"], "date": date, "start": start,
        "end": end, "note": entry["note"], "minutes": minutes, "times": _grid_times(minutes, (start, end))})


def _form_to_range(date, start, end, zone):
    """Local date + "HH:MM" from/to -> UTC ISO pair (an end before the start
    means past midnight)."""
    if not (date and start and end):
        raise HTTPException(400, "Projekt, Datum, Von und Bis sind erforderlich")
    if start == end:
        raise HTTPException(400, "Bis muss nach Von liegen")
    try:
        begin = datetime.fromisoformat(f"{date}T{start}").replace(tzinfo=zone)
        finish = datetime.fromisoformat(f"{date}T{end}").replace(tzinfo=zone)
    except ValueError:
        raise HTTPException(400, "Ungültige Zeitangabe")
    if finish < begin:
        finish += timedelta(days=1)
    return _iso(begin.astimezone(timezone.utc)), _iso(finish.astimezone(timezone.utc))


@router.post("/hx/time-tracking/entries")
def hx_create(request: Request, project_id: int = Form(...), date: str = Form(""), start: str = Form(""),
              end: str = Form(""), note: str = Form("")):
    started_at, ended_at = _form_to_range(date, start, end, client_zone(request))
    add_time_entry(TimeEntryIn(project_id=project_id, started_at=started_at, ended_at=ended_at, note=note.strip()))
    return _changed({"hx-modal-close": True})


@router.put("/hx/time-tracking/entries/{entry_id}")
def hx_update(request: Request, entry_id: int, project_id: int = Form(...), date: str = Form(""),
              start: str = Form(""), end: str = Form(""), note: str = Form("")):
    """Times left as shown are sent back verbatim (update_time_entry then
    keeps the stored values instead of re-snapping them to the current grid)."""
    zone = client_zone(request)
    entry = next((e for e in list_time_entries() if e["id"] == entry_id), None)
    if not entry:
        raise HTTPException(404, "Eintrag nicht gefunden")
    shown = (*_local_parts(entry["started_at"], zone), _local_parts(entry["ended_at"], zone)[1])
    if (date, start, end) == shown:
        started_at, ended_at = entry["started_at"], entry["ended_at"]
    else:
        started_at, ended_at = _form_to_range(date, start, end, zone)
    update_time_entry(entry_id, TimeEntryIn(project_id=project_id, started_at=started_at, ended_at=ended_at, note=note.strip()))
    return _changed({"hx-modal-close": True})
