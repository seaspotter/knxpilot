"""
Klärungsliste sub-tab: per-project list of open questions/tasks/notes for
site visits, optionally tied to a room or a specific room point. Internal
only - does not appear in the Pflichtenheft export. The one thing that
does leave the app is the "Offene Punkte" export (PDF, or the same list
as plain text copied in the browser) - still-open entries only, meant to
be sent to the customer/electrician to get them answered.
"""
from datetime import datetime
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table

from ..db import get_db
from ..models import KlaerungIn
from ..pdf_design import (
    build_pdf_bytes, company_footer_line, company_header_block, pdf_response, pdf_styles, pdf_table_style,
    pdf_title_banner,
)
from ..utils import AGED_KLAERUNG_DAYS

router = APIRouter(tags=["klaerungsliste"])


@router.get("/api/projects/{project_id}/klaerungen")
def list_klaerungen(project_id: int):
    with get_db() as db:
        rows = db.execute(
            "SELECT k.*, r.name AS room_name, rp.label AS point_label, "
            "CAST(julianday('now') - julianday(k.created_at) AS INTEGER) AS age_days "
            "FROM klaerungen k "
            "LEFT JOIN rooms r ON k.room_id = r.id "
            "LEFT JOIN room_points rp ON k.room_point_id = rp.id "
            "WHERE k.project_id=? ORDER BY k.room_id IS NULL DESC, k.order_idx",
            (project_id,),
        ).fetchall()
        return [
            {
                "id": r["id"], "room_id": r["room_id"], "room_point_id": r["room_point_id"],
                "room_name": r["room_name"], "point_label": r["point_label"],
                "text": r["text"], "typ": r["typ"], "status": r["status"], "antwort": r["antwort"],
                "age_days": r["age_days"] or 0,
                "aged": r["status"] == "offen" and (r["age_days"] or 0) >= AGED_KLAERUNG_DAYS,
            }
            for r in rows
        ]


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
