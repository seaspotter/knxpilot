"""
Klärungsliste sub-tab: per-project list of open questions/tasks/notes for
site visits, optionally tied to a room or a specific room point. Internal
only - does not appear in the Pflichtenheft export. The one thing that
does leave the app is the "Offene Punkte" export (PDF, or the same list
as plain text copied in the browser) - still-open entries only, meant to
be sent to the customer/electrician to get them answered.

This tab is the first one rendered server-side with htmx (see
DEVELOPMENT.md "htmx tabs"): the /hx/... endpoints below return HTML
fragments from backend/templates/klaerungsliste/, and the browser swaps
them in - there is no client-side state. The JSON endpoints stay for the
subnav badge, the exports and the tests.
"""
import json
from datetime import datetime
from xml.sax.saxutils import escape

from fastapi import APIRouter, Form, HTTPException, Request
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table

from ..db import get_db
from ..models import KlaerungIn
from ..pdf_design import (
    build_pdf_bytes, company_footer_line, company_header_block, pdf_response, pdf_styles, pdf_table_style,
    pdf_title_banner,
)
from ..templating import templates
from ..utils import AGED_KLAERUNG_DAYS

router = APIRouter(tags=["klaerungsliste"])

KLAERUNG_TYPES = ["Frage", "Aufgabe", "Notiz"]
KLAERUNG_STATUSES = ["offen", "geklärt", "abgelehnt"]


def _klaerungen(db, project_id):
    """Every entry in list order (Allgemein first, then by room in the order
    entries were added), with room/point labels and age."""
    rows = db.execute(
        "SELECT k.*, r.name AS room_name, f.name AS floor_name, rp.label AS point_label, "
        "CAST(julianday('now') - julianday(k.created_at) AS INTEGER) AS age_days "
        "FROM klaerungen k "
        "LEFT JOIN rooms r ON k.room_id = r.id "
        "LEFT JOIN floors f ON r.floor_id = f.id "
        "LEFT JOIN room_points rp ON k.room_point_id = rp.id "
        "WHERE k.project_id=? ORDER BY k.room_id IS NULL DESC, k.order_idx",
        (project_id,),
    ).fetchall()
    return [
        {
            "id": r["id"], "room_id": r["room_id"], "room_point_id": r["room_point_id"],
            "room_name": r["room_name"], "point_label": r["point_label"],
            "group_label": f"{r['floor_name']} — {r['room_name']}" if r["room_name"] else "Allgemein",
            "text": r["text"], "typ": r["typ"], "status": r["status"], "antwort": r["antwort"],
            "age_days": r["age_days"] or 0,
            "aged": r["status"] == "offen" and (r["age_days"] or 0) >= AGED_KLAERUNG_DAYS,
        }
        for r in rows
    ]


@router.get("/api/projects/{project_id}/klaerungen")
def list_klaerungen(project_id: int):
    with get_db() as db:
        return [{k: v for k, v in e.items() if k != "group_label"} for e in _klaerungen(db, project_id)]


@router.post("/api/projects/{project_id}/klaerungen")
def add_klaerung(project_id: int, k: KlaerungIn):
    with get_db() as db:
        (count,) = db.execute(
            "SELECT COUNT(*) FROM klaerungen WHERE project_id=?", (project_id,)
        ).fetchone()
        cur = db.execute(
            "INSERT INTO klaerungen (project_id, room_id, room_point_id, text, typ, status, antwort, order_idx) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, k.room_id, k.room_point_id, k.text, k.typ, k.status, k.antwort, count),
        )
        return {"id": cur.lastrowid}


@router.put("/api/klaerungen/{k_id}")
def update_klaerung(k_id: int, k: KlaerungIn):
    with get_db() as db:
        db.execute(
            "UPDATE klaerungen SET room_id=?, room_point_id=?, text=?, typ=?, status=?, antwort=? WHERE id=?",
            (k.room_id, k.room_point_id, k.text, k.typ, k.status, k.antwort, k_id),
        )
    return {"ok": True}


@router.delete("/api/klaerungen/{k_id}")
def delete_klaerung(k_id: int):
    with get_db() as db:
        db.execute("DELETE FROM klaerungen WHERE id=?", (k_id,))
    return {"ok": True}


def open_klaerungen_grouped(db, project_id):
    """Still-open entries as [(group_label, [entry, ...]), ...], in the same
    order the Klärungsliste tab shows them (Allgemein first, then rooms by
    first appearance) and numbered consecutively across groups - so the PDF
    and the tab's "Als Text kopieren" list use identical numbers."""
    rows = db.execute(
        "SELECT k.*, r.name AS room_name, f.name AS floor_name, rp.label AS point_label "
        "FROM klaerungen k "
        "LEFT JOIN rooms r ON k.room_id = r.id "
        "LEFT JOIN floors f ON r.floor_id = f.id "
        "LEFT JOIN room_points rp ON k.room_point_id = rp.id "
        "WHERE k.project_id=? AND k.status='offen' ORDER BY k.room_id IS NULL DESC, k.order_idx",
        (project_id,),
    ).fetchall()
    groups = {}
    for r in rows:
        label = f"{r['floor_name']} — {r['room_name']}" if r["room_name"] else "Allgemein"
        groups.setdefault(label, []).append(dict(r))
    # Numbered after grouping, so the numbers run 1, 2, 3... down the page.
    n = 0
    for entries in groups.values():
        for e in entries:
            n += 1
            e["nr"] = n
    return list(groups.items())


def build_klaerungsliste_pdf_bytes(project_id: int):
    """"Offene Punkte" PDF: every still-open Klärungsliste entry, grouped by
    room, with an Antwort column - pre-filled if an answer was already noted,
    otherwise left empty to be filled in by hand. Shared by the download
    endpoint below and routers/email.py's send-by-mail action."""
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        groups = open_klaerungen_grouped(db, project_id)

    styles = pdf_styles()
    story = company_header_block(company) + pdf_title_banner(
        f"Offene Punkte — {project['name']}", f"Klärungsliste · Stand {datetime.now():%d.%m.%Y}"
    )
    if not groups:
        story.append(Paragraph("Keine offenen Punkte.", styles["BodyMuted"]))
    cell = lambda text: Paragraph(escape(text or ""), styles["TableCell"])
    for label, entries in groups:
        table_data = [["Nr.", "Typ", "Frage / Aufgabe", "Antwort"]]
        for e in entries:
            text = e["text"] + (f" (Punkt: {e['point_label']})" if e["point_label"] else "")
            table_data.append([cell(str(e["nr"])), cell(e["typ"]), cell(text), cell(e["antwort"])])
        table = Table(table_data, colWidths=[12 * mm, 20 * mm, 78 * mm, 70 * mm], repeatRows=1)
        # Taller rows leave room to write an answer by hand on a printout.
        table.setStyle(pdf_table_style([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 1), (-1, -1), 14)]))
        story.append(KeepTogether([Paragraph(escape(label), styles["RoomHeading"]), table]))
        story.append(Spacer(1, 3 * mm))

    data = build_pdf_bytes(
        story,
        footer_left_text=f"Offene Punkte · {project['name']}",
        doc_title=f"Offene Punkte {project['name']}",
        footer_center_text=company_footer_line(company),
    )
    return data, f"{project['name'].replace(' ', '_')}_offene_punkte.pdf"


@router.get("/api/projects/{project_id}/export-klaerungsliste.pdf")
def export_klaerungsliste_pdf(project_id: int):
    data, filename = build_klaerungsliste_pdf_bytes(project_id)
    return pdf_response(data, filename)


def open_klaerungen_text(db, project_id):
    """The "Als Text kopieren" list - same grouping and numbers as the PDF
    (open_klaerungen_grouped), rendered into the tab so the copy button
    works without a request (clipboard access needs the click itself)."""
    groups = open_klaerungen_grouped(db, project_id)
    if not groups:
        return ""
    project = db.execute("SELECT name FROM projects WHERE id=?", (project_id,)).fetchone()
    lines = [f"Offene Punkte – {project['name']} (Stand {datetime.now():%d.%m.%Y})", ""]
    for label, entries in groups:
        lines.append(label)
        for e in entries:
            lines.append(f"{e['nr']}. [{e['typ']}] {e['text']}" + (f" (Punkt: {e['point_label']})" if e["point_label"] else ""))
            if e["antwort"]:
                lines.append(f"   Bisher: {e['antwort']}")
        lines.append("")
    return "\n".join(lines).strip()


# ---------- htmx fragments (backend/templates/klaerungsliste/) ----------
def _rooms_with_points(db, project_id):
    rooms = []
    for floor in db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall():
        for room in db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall():
            points = db.execute(
                "SELECT id, label FROM room_points WHERE room_id=? ORDER BY order_idx", (room["id"],)
            ).fetchall()
            rooms.append({"id": room["id"], "label": f"{floor['name']} — {room['name']}",
                          "points": [dict(p) for p in points]})
    return rooms


def _form_context(db, project_id, entry=None):
    rooms = _rooms_with_points(db, project_id)
    room = next((r for r in rooms if entry and r["id"] == entry["room_id"]), None)
    return {"project_id": project_id, "entry": entry, "rooms": rooms, "types": KLAERUNG_TYPES,
            "points": room["points"] if room else [], "selected_point": entry["room_point_id"] if entry else None}


def _list_context(db, project_id):
    entries = _klaerungen(db, project_id)
    groups = {}
    for e in entries:
        groups.setdefault(e["group_label"], []).append(e)
    return {"project_id": project_id, "groups": list(groups.items()),
            "aged_count": sum(e["aged"] for e in entries), "aged_days": AGED_KLAERUNG_DAYS,
            "statuses": KLAERUNG_STATUSES, "open_text": open_klaerungen_text(db, project_id),
            "open_count": sum(e["status"] == "offen" for e in entries)}


def _render(request, name, context, headers=None):
    """Every fragment that shows the list also tells the page the new counts
    (HX-Trigger), so the subnav badge "Klärungsliste (n)" stays current."""
    response = templates.TemplateResponse(request, name, context)
    if "open_count" in context:
        response.headers["HX-Trigger"] = json.dumps(
            {"klaerungen-changed": {"open": context["open_count"], "aged": context["aged_count"]}})
    return response


def _project_of(db, k_id):
    row = db.execute("SELECT project_id FROM klaerungen WHERE id=?", (k_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Eintrag nicht mehr vorhanden")
    return row["project_id"]


def _int_or_none(value):
    return int(value) if value not in (None, "") else None


def _tab(request, db, project_id):
    return _render(request, "klaerungsliste/tab.html", {**_form_context(db, project_id), **_list_context(db, project_id)})


def _list(request, db, project_id):
    return _render(request, "klaerungsliste/_list.html", _list_context(db, project_id))


@router.get("/hx/projects/{project_id}/klaerungsliste")
def hx_tab(request: Request, project_id: int):
    with get_db() as db:
        return _tab(request, db, project_id)


@router.get("/hx/projects/{project_id}/klaerungsliste/form")
def hx_form(request: Request, project_id: int):
    """The empty "Neuer Eintrag" form (e.g. "Abbrechen" while editing)."""
    with get_db() as db:
        return _render(request, "klaerungsliste/_form.html", _form_context(db, project_id))


@router.get("/hx/klaerungsliste/points")
def hx_points(request: Request, room_id: str = ""):
    """The point <select> for the chosen room (empty for Allgemein/no points)."""
    points = []
    if room_id:
        with get_db() as db:
            points = [dict(p) for p in db.execute(
                "SELECT id, label FROM room_points WHERE room_id=? ORDER BY order_idx", (int(room_id),)).fetchall()]
    return _render(request, "klaerungsliste/_points.html", {"points": points, "selected_point": None})


@router.post("/hx/projects/{project_id}/klaerungen")
def hx_create(request: Request, project_id: int, text: str = Form(""), typ: str = Form("Frage"),
              room_id: str = Form(""), room_point_id: str = Form("")):
    if not text.strip():
        raise HTTPException(400, "Text ist erforderlich")
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM klaerungen WHERE project_id=?", (project_id,)).fetchone()
        db.execute(
            "INSERT INTO klaerungen (project_id, room_id, room_point_id, text, typ, order_idx) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, _int_or_none(room_id), _int_or_none(room_point_id), text.strip(), typ, count),
        )
        return _tab(request, db, project_id)


@router.get("/hx/klaerungen/{k_id}/edit")
def hx_edit_form(request: Request, k_id: int):
    with get_db() as db:
        project_id = _project_of(db, k_id)
        entry = next(e for e in _klaerungen(db, project_id) if e["id"] == k_id)
        return _render(request, "klaerungsliste/_form.html", _form_context(db, project_id, entry))


@router.put("/hx/klaerungen/{k_id}")
def hx_update(request: Request, k_id: int, text: str = Form(""), typ: str = Form("Frage"),
              room_id: str = Form(""), room_point_id: str = Form("")):
    if not text.strip():
        raise HTTPException(400, "Text ist erforderlich")
    with get_db() as db:
        project_id = _project_of(db, k_id)
        db.execute("UPDATE klaerungen SET text=?, typ=?, room_id=?, room_point_id=? WHERE id=?",
                   (text.strip(), typ, _int_or_none(room_id), _int_or_none(room_point_id), k_id))
        return _tab(request, db, project_id)


@router.post("/hx/klaerungen/{k_id}/status")
def hx_status(request: Request, k_id: int, status: str = Form(...)):
    if status not in KLAERUNG_STATUSES:
        raise HTTPException(400, "Unbekannter Status")
    with get_db() as db:
        project_id = _project_of(db, k_id)
        db.execute("UPDATE klaerungen SET status=? WHERE id=?", (status, k_id))
        return _list(request, db, project_id)


@router.post("/hx/klaerungen/{k_id}/antwort")
def hx_antwort(request: Request, k_id: int, antwort: str = Form("")):
    """Saved on change without re-rendering (keeps focus/cursor); only the
    hidden "Als Text kopieren" text is refreshed, out of band."""
    with get_db() as db:
        project_id = _project_of(db, k_id)
        db.execute("UPDATE klaerungen SET antwort=? WHERE id=?", (antwort.strip(), k_id))
        return _render(request, "klaerungsliste/_open_text.html",
                       {"open_text": open_klaerungen_text(db, project_id), "oob": True})


@router.delete("/hx/klaerungen/{k_id}")
def hx_delete(request: Request, k_id: int):
    with get_db() as db:
        project_id = _project_of(db, k_id)
        db.execute("DELETE FROM klaerungen WHERE id=?", (k_id,))
        return _list(request, db, project_id)
