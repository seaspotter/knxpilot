"""
Verteilerplanung tab: a simple visual DIN-rail cabinet layout per Geschoss.
Fixed 12-TE-wide rows; each row holds RCD/LS-Schalter blocks (simple labeled/
sized placeholders, no link to specific circuits) and/or actor instances
already placed via the Abgangsliste tab (their width comes live from
actor_types.width_te).
"""
from fastapi import APIRouter, HTTPException
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from ..db import get_db
from ..models import VerteilerIn, VerteilerUpdateIn, VerteilerItemIn, VerteilerItemMoveIn
from ..pdf_design import (
    pdf_styles, pdf_title_banner, build_pdf_response, company_header_block, company_footer_line,
    PDF_BORDER_COLOR,
)
from ..utils import join_parts

router = APIRouter(tags=["verteiler"])

ROW_WIDTH_TE = 12
DEFAULT_WIDTH_TE = {"rcd": 4, "ls": 1}
ROW_TABLE_WIDTH_MM = 170
_PDF_PROTECTIVE_COLOR = colors.HexColor("#e2e8f0")
_PDF_DEVICE_COLOR = colors.HexColor("#fef3c7")


def _serialize_verteiler(db, row):
    items = db.execute(
        "SELECT vi.*, "
        "ai.location_label as ai_location_label, ai.physical_address as ai_physical_address, "
        "at.manufacturer as at_manufacturer, at.model as at_model, at.width_te as at_width_te "
        "FROM verteiler_items vi "
        "LEFT JOIN actor_instances ai ON vi.actor_instance_id = ai.id "
        "LEFT JOIN actor_types at ON ai.actor_type_id = at.id "
        "WHERE vi.verteiler_id=? ORDER BY vi.row_idx, vi.position_idx",
        (row["id"],),
    ).fetchall()

    rows = [[] for _ in range(row["row_count"])]
    for it in items:
        if it["item_type"] == "device":
            width_te = it["at_width_te"]
            label = join_parts(it["at_manufacturer"], it["at_model"]) or "?"
            sublabel = it["ai_physical_address"]
            location_label = it["ai_location_label"]
        else:
            width_te = it["width_te"]
            label = it["label"] or ("RCD" if it["item_type"] == "rcd" else "LS")
            sublabel = ""
            location_label = ""
        entry = {
            "id": it["id"], "item_type": it["item_type"], "width_te": width_te,
            "label": label, "sublabel": sublabel, "location_label": location_label,
            "actor_instance_id": it["actor_instance_id"],
        }
        if 0 <= it["row_idx"] < len(rows):
            rows[it["row_idx"]].append(entry)

    return {
        "id": row["id"], "floor_id": row["floor_id"], "name": row["name"],
        "row_count": row["row_count"], "row_width_te": ROW_WIDTH_TE, "rows": rows,
    }


@router.get("/api/projects/{project_id}/verteiler")
def list_verteiler(project_id: int):
    with get_db() as db:
        floors = {r["id"]: r["name"] for r in db.execute("SELECT * FROM floors WHERE project_id=?", (project_id,)).fetchall()}
        rows = db.execute(
            "SELECT * FROM verteiler WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall()
        result = []
        for row in rows:
            v = _serialize_verteiler(db, row)
            v["floor_name"] = floors.get(row["floor_id"], "")
            result.append(v)
        return result


@router.post("/api/projects/{project_id}/verteiler")
def create_verteiler(project_id: int, v: VerteilerIn):
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM verteiler WHERE project_id=?", (project_id,)).fetchone()
        cur = db.execute(
            "INSERT INTO verteiler (project_id, floor_id, name, row_count, order_idx) VALUES (?, ?, ?, ?, ?)",
            (project_id, v.floor_id, v.name, max(1, v.row_count), count),
        )
        return {"id": cur.lastrowid}


@router.put("/api/verteiler/{verteiler_id}")
def update_verteiler(verteiler_id: int, v: VerteilerUpdateIn):
    with get_db() as db:
        (max_row,) = db.execute(
            "SELECT COALESCE(MAX(row_idx), -1) FROM verteiler_items WHERE verteiler_id=?", (verteiler_id,)
        ).fetchone()
        if v.row_count < max_row + 1:
            raise HTTPException(400, f"Reihe {max_row + 1} enthält noch Elemente - erst leeren oder umziehen")
        db.execute(
            "UPDATE verteiler SET name=?, row_count=? WHERE id=?",
            (v.name, max(1, v.row_count), verteiler_id),
        )
    return {"ok": True}


@router.delete("/api/verteiler/{verteiler_id}")
def delete_verteiler(verteiler_id: int):
    with get_db() as db:
        db.execute("DELETE FROM verteiler WHERE id=?", (verteiler_id,))
    return {"ok": True}


@router.post("/api/verteiler/{verteiler_id}/items")
def add_verteiler_item(verteiler_id: int, item: VerteilerItemIn):
    with get_db() as db:
        v = db.execute("SELECT * FROM verteiler WHERE id=?", (verteiler_id,)).fetchone()
        if not v:
            raise HTTPException(404, "Verteiler not found")
        if item.row_idx < 0 or item.row_idx >= v["row_count"]:
            raise HTTPException(400, "Ungültige Reihe")

        if item.item_type == "device":
            if not item.actor_instance_id:
                raise HTTPException(400, "Gerät fehlt")
            ai = db.execute(
                "SELECT ai.*, at.width_te as at_width_te FROM actor_instances ai "
                "JOIN actor_types at ON ai.actor_type_id = at.id WHERE ai.id=?",
                (item.actor_instance_id,),
            ).fetchone()
            if not ai:
                raise HTTPException(404, "Gerät nicht gefunden")
            if ai["at_width_te"] is None:
                raise HTTPException(400, "Diesem Gerät fehlt eine TE-Breite im Geräte-Katalog")
            already = db.execute(
                "SELECT 1 FROM verteiler_items WHERE actor_instance_id=?", (item.actor_instance_id,)
            ).fetchone()
            if already:
                raise HTTPException(400, "Dieses Gerät ist bereits in einem Verteiler platziert")
            width_te = ai["at_width_te"]
            label = ""
        elif item.item_type in ("rcd", "ls"):
            width_te = item.width_te or DEFAULT_WIDTH_TE[item.item_type]
            label = item.label
        else:
            raise HTTPException(400, "Unbekannter item_type")

        (used,) = db.execute(
            "SELECT COALESCE(SUM(CASE WHEN vi.item_type='device' THEN at.width_te ELSE vi.width_te END), 0) "
            "FROM verteiler_items vi "
            "LEFT JOIN actor_instances ai ON vi.actor_instance_id = ai.id "
            "LEFT JOIN actor_types at ON ai.actor_type_id = at.id "
            "WHERE vi.verteiler_id=? AND vi.row_idx=?",
            (verteiler_id, item.row_idx),
        ).fetchone()
        free = ROW_WIDTH_TE - used
        if width_te > free:
            raise HTTPException(400, f"Reihe ist voll (nur noch {free} TE frei)")

        (next_pos,) = db.execute(
            "SELECT COALESCE(MAX(position_idx) + 1, 0) FROM verteiler_items WHERE verteiler_id=? AND row_idx=?",
            (verteiler_id, item.row_idx),
        ).fetchone()
        cur = db.execute(
            "INSERT INTO verteiler_items (verteiler_id, row_idx, position_idx, item_type, label, width_te, actor_instance_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (verteiler_id, item.row_idx, next_pos, item.item_type, label,
             width_te if item.item_type in ("rcd", "ls") else None, item.actor_instance_id),
        )
        return {"id": cur.lastrowid}


@router.delete("/api/verteiler-items/{item_id}")
def delete_verteiler_item(item_id: int):
    with get_db() as db:
        db.execute("DELETE FROM verteiler_items WHERE id=?", (item_id,))
    return {"ok": True}


@router.post("/api/verteiler-items/{item_id}/move")
def move_verteiler_item(item_id: int, m: VerteilerItemMoveIn):
    with get_db() as db:
        it = db.execute("SELECT * FROM verteiler_items WHERE id=?", (item_id,)).fetchone()
        if not it:
            raise HTTPException(404, "Item not found")
        op = "<" if m.direction == "left" else ">"
        order = "DESC" if m.direction == "left" else "ASC"
        neighbor = db.execute(
            f"SELECT * FROM verteiler_items WHERE verteiler_id=? AND row_idx=? AND position_idx {op} ? "
            f"ORDER BY position_idx {order} LIMIT 1",
            (it["verteiler_id"], it["row_idx"], it["position_idx"]),
        ).fetchone()
        if not neighbor:
            return {"ok": True}
        db.execute("UPDATE verteiler_items SET position_idx=? WHERE id=?", (neighbor["position_idx"], it["id"]))
        db.execute("UPDATE verteiler_items SET position_idx=? WHERE id=?", (it["position_idx"], neighbor["id"]))
    return {"ok": True}


# --------------------------------------------------------------------------
# PDF export
# --------------------------------------------------------------------------
def _verteiler_row_table(row_items, row_width_te, styles):
    """One reportlab Table per DIN-rail row, cell widths proportional to each
    item's TE share - mirrors the browser's flex-basis rendering directly, so
    the printed layout matches what's on screen. Free space becomes its own
    muted cell, same as the dashed placeholder in the UI."""
    if not row_items and row_width_te <= 0:
        return None
    # ALIGN in the TableStyle below only centers the Paragraph flowable within
    # its cell - since each Paragraph already fills the full cell width, the
    # text inside it still renders left-justified unless the *style itself*
    # centers it, hence these cloned variants rather than reusing styles[...]
    # directly.
    body_center = styles["Body"].clone("VerteilerBody", alignment=TA_CENTER)
    muted_center = styles["BodyMuted"].clone("VerteilerBodyMuted", alignment=TA_CENTER)

    cells, widths, bg_commands = [], [], []
    for i, it in enumerate(row_items):
        w = it["width_te"] or 0
        widths.append(max(w, 0.5) / row_width_te * ROW_TABLE_WIDTH_MM * mm)
        text = f"<b>{it['label']}</b>"
        if it["sublabel"]:
            text += f"<br/>{it['sublabel']}"
        cells.append(Paragraph(text, body_center))
        bg = _PDF_DEVICE_COLOR if it["item_type"] == "device" else _PDF_PROTECTIVE_COLOR
        bg_commands.append(("BACKGROUND", (i, 0), (i, 0), bg))

    used = sum(it["width_te"] or 0 for it in row_items)
    free = row_width_te - used
    if free > 0:
        widths.append(free / row_width_te * ROW_TABLE_WIDTH_MM * mm)
        cells.append(Paragraph(f"{free} TE frei", muted_center))

    if not cells:
        return None
    table = Table([cells], colWidths=widths, rowHeights=[16 * mm])
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, PDF_BORDER_COLOR),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        *bg_commands,
    ]))
    return table


def build_verteilerplanung_story(db, project_id, styles):
    """The per-Verteiler/per-row content, as a list of flowables - factored out
    so both the standalone export below and the Pflichtenheft's optional
    inclusion (see pflichtenheft.py's pflichtenheft_include_verteilerplanung
    toggle) share one rendering, same pattern as build_abgangsliste_story."""
    floors = {r["id"]: r["name"] for r in db.execute("SELECT * FROM floors WHERE project_id=?", (project_id,)).fetchall()}
    verteiler_rows = db.execute(
        "SELECT * FROM verteiler WHERE project_id=? ORDER BY order_idx", (project_id,)
    ).fetchall()

    story = []
    if not verteiler_rows:
        story.append(Paragraph("Noch keine Verteiler angelegt.", styles["BodyMuted"]))
        return story

    for i, v in enumerate(verteiler_rows):
        if i > 0:
            story.append(Spacer(1, 6 * mm))
        serialized = _serialize_verteiler(db, v)
        floor_name = floors.get(v["floor_id"], "")
        heading = v["name"] or "Verteiler"
        if floor_name:
            heading += f" — {floor_name}"
        story.append(Paragraph(heading, styles["RoomHeading"]))
        for row_items in serialized["rows"]:
            table = _verteiler_row_table(row_items, serialized["row_width_te"], styles)
            if table:
                story.append(table)
                story.append(Spacer(1, 2 * mm))

    return story


@router.get("/api/projects/{project_id}/export-verteilerplanung.pdf")
def export_verteilerplanung_pdf(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        styles = pdf_styles()
        story = company_header_block(company) + pdf_title_banner(
            f"Verteilerplanung — {project['name']}", "Schaltschrank-Layout je Geschoss",
        )
        story += build_verteilerplanung_story(db, project_id, styles)

        return build_pdf_response(
            story,
            footer_left_text=f"Verteilerplanung · {project['name']}",
            filename=f"{project['name'].replace(' ', '_')}_verteilerplanung.pdf",
            doc_title=f"Verteilerplanung {project['name']}",
            footer_center_text=company_footer_line(company),
        )
