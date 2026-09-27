"""
Distribution board planning tab: a simple visual DIN-rail cabinet layout per
Geschoss. Fixed 12-TE-wide rows; each row holds RCD/LS-Schalter blocks
(simple labeled/sized placeholders, no link to specific circuits) and/or
actor instances already placed via the Abgangsliste tab (their width comes
live from actor_types.width_te).

Rendered server-side with htmx (see DEVELOPMENT.md "htmx tabs"): the /hx/...
endpoints below return HTML fragments from
backend/templates/distribution_boards/, and the browser swaps them in -
there is no client-side state. The JSON endpoints stay for the project-tree
drag & drop (Gebäudestruktur sub-tab, still classic JS) and the tests.
"""
from fastapi import APIRouter, Form, HTTPException, Request
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from ..db import get_db
from ..models import (
    DistributionBoardIn, DistributionBoardItemIn, DistributionBoardItemMoveIn, DistributionBoardUpdateIn,
    DistributionBoardLocationIn,
)
from ..pdf_design import (
    pdf_styles, pdf_title_banner, build_pdf_response, company_header_block, company_footer_line,
    PDF_BORDER_COLOR,
)
from ..templating import templates
from ..utils import join_parts

router = APIRouter(tags=["distribution-boards"])

ROW_WIDTH_TE = 12
DEFAULT_WIDTH_TE = {"rcd": 4, "ls": 1}
ROW_TABLE_WIDTH_MM = 170
_PDF_PROTECTIVE_COLOR = colors.HexColor("#e2e8f0")
_PDF_DEVICE_COLOR = colors.HexColor("#fef3c7")


def _serialize_board(db, row):
    items = db.execute(
        "SELECT dbi.*, "
        "ai.location_label as ai_location_label, ai.physical_address as ai_physical_address, "
        "at.manufacturer as at_manufacturer, at.model as at_model, at.width_te as at_width_te "
        "FROM distribution_board_items dbi "
        "LEFT JOIN actor_instances ai ON dbi.actor_instance_id = ai.id "
        "LEFT JOIN actor_types at ON ai.actor_type_id = at.id "
        "WHERE dbi.distribution_board_id=? ORDER BY dbi.row_idx, dbi.position_idx",
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
        "id": row["id"], "floor_id": row["floor_id"], "room_id": row["room_id"], "name": row["name"],
        "row_count": row["row_count"], "row_width_te": ROW_WIDTH_TE, "rows": rows,
    }


@router.get("/api/projects/{project_id}/distribution-boards")
def list_distribution_boards(project_id: int):
    with get_db() as db:
        floors = {r["id"]: r["name"] for r in db.execute("SELECT * FROM floors WHERE project_id=?", (project_id,)).fetchall()}
        rooms = {r["id"]: r["name"] for r in db.execute(
            "SELECT r.id, r.name FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE f.project_id=?", (project_id,))}
        rows = db.execute(
            "SELECT * FROM distribution_boards WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall()
        result = []
        for row in rows:
            board = _serialize_board(db, row)
            board["floor_name"] = floors.get(row["floor_id"], "")
            board["room_name"] = rooms.get(row["room_id"], "")
            result.append(board)
        return result


def _resolve_location(db, project_id, floor_id, room_id):
    """(floor_id, room_id) for a distribution board - a room implies its
    floor, and both have to belong to the project."""
    if room_id is not None:
        room = db.execute(
            "SELECT r.floor_id FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE r.id=? AND f.project_id=?",
            (room_id, project_id),
        ).fetchone()
        if not room:
            raise HTTPException(400, "Raum gehört nicht zu diesem Projekt")
        return room["floor_id"], room_id
    if floor_id is not None and not db.execute(
        "SELECT 1 FROM floors WHERE id=? AND project_id=?", (floor_id, project_id)
    ).fetchone():
        raise HTTPException(400, "Geschoss gehört nicht zu diesem Projekt")
    return floor_id, None


@router.post("/api/projects/{project_id}/distribution-boards")
def create_distribution_board(project_id: int, board: DistributionBoardIn):
    with get_db() as db:
        floor_id, room_id = _resolve_location(db, project_id, board.floor_id, board.room_id)
        (count,) = db.execute("SELECT COUNT(*) FROM distribution_boards WHERE project_id=?", (project_id,)).fetchone()
        cur = db.execute(
            "INSERT INTO distribution_boards (project_id, floor_id, room_id, name, row_count, order_idx) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, floor_id, room_id, board.name, max(1, board.row_count), count),
        )
        return {"id": cur.lastrowid}


@router.put("/api/distribution-boards/{board_id}/location")
def set_distribution_board_location(board_id: int, loc: DistributionBoardLocationIn):
    """Gebäudestruktur drag & drop: put a distribution board on a Geschoss or into a room."""
    with get_db() as db:
        row = db.execute("SELECT project_id FROM distribution_boards WHERE id=?", (board_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Verteiler not found")
        floor_id, room_id = _resolve_location(db, row["project_id"], loc.floor_id, loc.room_id)
        db.execute("UPDATE distribution_boards SET floor_id=?, room_id=? WHERE id=?", (floor_id, room_id, board_id))
    return {"ok": True}


@router.put("/api/distribution-boards/{board_id}")
def update_distribution_board(board_id: int, board: DistributionBoardUpdateIn):
    with get_db() as db:
        (max_row,) = db.execute(
            "SELECT COALESCE(MAX(row_idx), -1) FROM distribution_board_items WHERE distribution_board_id=?", (board_id,)
        ).fetchone()
        if board.row_count < max_row + 1:
            raise HTTPException(400, f"Reihe {max_row + 1} enthält noch Elemente - erst leeren oder umziehen")
        db.execute(
            "UPDATE distribution_boards SET name=?, row_count=? WHERE id=?",
            (board.name, max(1, board.row_count), board_id),
        )
    return {"ok": True}


@router.delete("/api/distribution-boards/{board_id}")
def delete_distribution_board(board_id: int):
    with get_db() as db:
        db.execute("DELETE FROM distribution_boards WHERE id=?", (board_id,))
    return {"ok": True}


@router.post("/api/distribution-boards/{board_id}/items")
def add_distribution_board_item(board_id: int, item: DistributionBoardItemIn):
    with get_db() as db:
        board = db.execute("SELECT * FROM distribution_boards WHERE id=?", (board_id,)).fetchone()
        if not board:
            raise HTTPException(404, "Verteiler not found")
        if item.row_idx < 0 or item.row_idx >= board["row_count"]:
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
                "SELECT 1 FROM distribution_board_items WHERE actor_instance_id=?", (item.actor_instance_id,)
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
            "SELECT COALESCE(SUM(CASE WHEN dbi.item_type='device' THEN at.width_te ELSE dbi.width_te END), 0) "
            "FROM distribution_board_items dbi "
            "LEFT JOIN actor_instances ai ON dbi.actor_instance_id = ai.id "
            "LEFT JOIN actor_types at ON ai.actor_type_id = at.id "
            "WHERE dbi.distribution_board_id=? AND dbi.row_idx=?",
            (board_id, item.row_idx),
        ).fetchone()
        free = ROW_WIDTH_TE - used
        if width_te > free:
            raise HTTPException(400, f"Reihe ist voll (nur noch {free} TE frei)")

        (next_pos,) = db.execute(
            "SELECT COALESCE(MAX(position_idx) + 1, 0) FROM distribution_board_items WHERE distribution_board_id=? AND row_idx=?",
            (board_id, item.row_idx),
        ).fetchone()
        cur = db.execute(
            "INSERT INTO distribution_board_items (distribution_board_id, row_idx, position_idx, item_type, label, width_te, actor_instance_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (board_id, item.row_idx, next_pos, item.item_type, label,
             width_te if item.item_type in ("rcd", "ls") else None, item.actor_instance_id),
        )
        return {"id": cur.lastrowid}


@router.delete("/api/distribution-board-items/{item_id}")
def delete_distribution_board_item(item_id: int):
    with get_db() as db:
        db.execute("DELETE FROM distribution_board_items WHERE id=?", (item_id,))
    return {"ok": True}


@router.post("/api/distribution-board-items/{item_id}/move")
def move_distribution_board_item(item_id: int, m: DistributionBoardItemMoveIn):
    with get_db() as db:
        it = db.execute("SELECT * FROM distribution_board_items WHERE id=?", (item_id,)).fetchone()
        if not it:
            raise HTTPException(404, "Item not found")
        op = "<" if m.direction == "left" else ">"
        order = "DESC" if m.direction == "left" else "ASC"
        neighbor = db.execute(
            f"SELECT * FROM distribution_board_items WHERE distribution_board_id=? AND row_idx=? AND position_idx {op} ? "
            f"ORDER BY position_idx {order} LIMIT 1",
            (it["distribution_board_id"], it["row_idx"], it["position_idx"]),
        ).fetchone()
        if not neighbor:
            return {"ok": True}
        db.execute("UPDATE distribution_board_items SET position_idx=? WHERE id=?", (neighbor["position_idx"], it["id"]))
        db.execute("UPDATE distribution_board_items SET position_idx=? WHERE id=?", (it["position_idx"], neighbor["id"]))
    return {"ok": True}


# --------------------------------------------------------------------------
# htmx fragments (backend/templates/distribution_boards/)
# --------------------------------------------------------------------------
def _floor_room_options(db, project_id):
    floors = []
    for floor in db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall():
        rooms = db.execute("SELECT id, name FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall()
        floors.append({"id": floor["id"], "name": floor["name"], "rooms": [dict(r) for r in rooms]})
    return floors


def _list_context(db, project_id):
    floors = {r["id"]: r["name"] for r in db.execute("SELECT * FROM floors WHERE project_id=?", (project_id,)).fetchall()}
    rooms = {r["id"]: r["name"] for r in db.execute(
        "SELECT r.id, r.name FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE f.project_id=?", (project_id,))}
    rows = db.execute("SELECT * FROM distribution_boards WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
    boards = []
    for row in rows:
        board = _serialize_board(db, row)
        board["floor_name"] = floors.get(row["floor_id"], "")
        board["room_name"] = rooms.get(row["room_id"], "")
        boards.append(board)
    return {"project_id": project_id, "boards": boards}


def _tab_context(db, project_id):
    return {**_list_context(db, project_id), "floors": _floor_room_options(db, project_id)}


def _list(request, db, project_id, close_modal=False):
    response = templates.TemplateResponse(request, "distribution_boards/_list.html", _list_context(db, project_id))
    if close_modal:
        response.headers["HX-Trigger"] = '{"hx-modal-close": true}'
    return response


@router.get("/hx/projects/{project_id}/distribution-boards")
def hx_tab(request: Request, project_id: int):
    with get_db() as db:
        return templates.TemplateResponse(request, "distribution_boards/tab.html", _tab_context(db, project_id))


@router.get("/hx/projects/{project_id}/distribution-boards/list")
def hx_list(request: Request, project_id: int):
    with get_db() as db:
        return _list(request, db, project_id)


def _int_or_none(value):
    return int(value) if value not in (None, "") else None


@router.post("/hx/projects/{project_id}/distribution-boards")
def hx_create(request: Request, project_id: int, location: str = Form(""), name: str = Form(""),
              row_count: int = Form(4)):
    kind, _, loc_id = location.partition(":")
    floor_id = int(loc_id) if kind == "floor" and loc_id else None
    room_id = int(loc_id) if kind == "room" and loc_id else None
    if floor_id is None and room_id is None:
        raise HTTPException(400, "Zuerst ein Geschoss in Gebäudestruktur anlegen")
    with get_db() as db:
        floor_id, room_id = _resolve_location(db, project_id, floor_id, room_id)
        (count,) = db.execute("SELECT COUNT(*) FROM distribution_boards WHERE project_id=?", (project_id,)).fetchone()
        db.execute(
            "INSERT INTO distribution_boards (project_id, floor_id, room_id, name, row_count, order_idx) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, floor_id, room_id, name.strip(), max(1, row_count), count),
        )
        return _list(request, db, project_id)


@router.get("/hx/distribution-boards/{board_id}/edit")
def hx_edit_form(request: Request, board_id: int):
    with get_db() as db:
        row = db.execute("SELECT * FROM distribution_boards WHERE id=?", (board_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Verteiler not found")
        return templates.TemplateResponse(request, "distribution_boards/_edit_form.html", {"board": dict(row)})


@router.put("/hx/distribution-boards/{board_id}")
def hx_update(request: Request, board_id: int, name: str = Form(""), row_count: int = Form(1)):
    with get_db() as db:
        row = db.execute("SELECT project_id FROM distribution_boards WHERE id=?", (board_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Verteiler not found")
        (max_row,) = db.execute(
            "SELECT COALESCE(MAX(row_idx), -1) FROM distribution_board_items WHERE distribution_board_id=?", (board_id,)
        ).fetchone()
        if row_count < max_row + 1:
            raise HTTPException(400, f"Reihe {max_row + 1} enthält noch Elemente - erst leeren oder umziehen")
        db.execute(
            "UPDATE distribution_boards SET name=?, row_count=? WHERE id=?",
            (name.strip(), max(1, row_count), board_id),
        )
        return _list(request, db, row["project_id"], close_modal=True)


@router.delete("/hx/distribution-boards/{board_id}")
def hx_delete(request: Request, board_id: int):
    with get_db() as db:
        row = db.execute("SELECT project_id FROM distribution_boards WHERE id=?", (board_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Verteiler not found")
        db.execute("DELETE FROM distribution_boards WHERE id=?", (board_id,))
        return _list(request, db, row["project_id"])


def _project_of_board(db, board_id):
    row = db.execute("SELECT project_id FROM distribution_boards WHERE id=?", (board_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Verteiler not found")
    return row["project_id"]


@router.post("/hx/distribution-boards/{board_id}/items")
def hx_add_item(request: Request, board_id: int, row_idx: int = Form(...), item_type: str = Form(...),
                actor_instance_id: str = Form("")):
    with get_db() as db:
        project_id = _project_of_board(db, board_id)
        item = DistributionBoardItemIn(
            row_idx=row_idx, item_type=item_type, actor_instance_id=_int_or_none(actor_instance_id),
        )
        add_distribution_board_item(board_id, item)
        return _list(request, db, project_id, close_modal=(item_type == "device"))


@router.get("/hx/distribution-boards/{board_id}/rows/{row_idx}/add-device")
def hx_add_device_form(request: Request, board_id: int, row_idx: int):
    with get_db() as db:
        board_row = db.execute("SELECT * FROM distribution_boards WHERE id=?", (board_id,)).fetchone()
        if not board_row:
            raise HTTPException(404, "Verteiler not found")
        placed = {r["actor_instance_id"] for r in db.execute(
            "SELECT actor_instance_id FROM distribution_board_items WHERE actor_instance_id IS NOT NULL").fetchall()}
        candidates = db.execute(
            "SELECT ai.id, ai.location_label, ai.physical_address, "
            "at.manufacturer as at_manufacturer, at.model as at_model, at.width_te as at_width_te "
            "FROM actor_instances ai JOIN actor_types at ON ai.actor_type_id = at.id "
            "WHERE ai.floor_id=? AND at.width_te IS NOT NULL ORDER BY ai.order_idx",
            (board_row["floor_id"],),
        ).fetchall()
        options = [
            {
                "id": c["id"], "width_te": c["at_width_te"],
                "label": join_parts(join_parts(c["at_manufacturer"], c["at_model"]), c["location_label"], c["physical_address"]),
            }
            for c in candidates if c["id"] not in placed
        ]
        return templates.TemplateResponse(request, "distribution_boards/_add_device_form.html", {
            "board_id": board_id, "row_idx": row_idx, "options": options,
        })


@router.delete("/hx/distribution-board-items/{item_id}")
def hx_delete_item(request: Request, item_id: int):
    with get_db() as db:
        row = db.execute("SELECT distribution_board_id FROM distribution_board_items WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Item not found")
        project_id = _project_of_board(db, row["distribution_board_id"])
        db.execute("DELETE FROM distribution_board_items WHERE id=?", (item_id,))
        return _list(request, db, project_id)


@router.post("/hx/distribution-board-items/{item_id}/move")
def hx_move_item(request: Request, item_id: int, direction: str = Form(...)):
    with get_db() as db:
        row = db.execute("SELECT distribution_board_id FROM distribution_board_items WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Item not found")
        project_id = _project_of_board(db, row["distribution_board_id"])
        move_distribution_board_item(item_id, DistributionBoardItemMoveIn(direction=direction))
        return _list(request, db, project_id)


# --------------------------------------------------------------------------
# PDF export
# --------------------------------------------------------------------------
def _board_row_table(row_items, row_width_te, styles):
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
    body_center = styles["Body"].clone("DistributionBoardBody", alignment=TA_CENTER)
    muted_center = styles["BodyMuted"].clone("DistributionBoardBodyMuted", alignment=TA_CENTER)

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


def build_distribution_boards_story(db, project_id, styles):
    """The per-board/per-row content, as a list of flowables - factored out
    so both the standalone export below and the Pflichtenheft's optional
    inclusion (see documentation.py's documentation_include_distribution_boards
    toggle) share one rendering, same pattern as build_circuit_list_story."""
    floors = {r["id"]: r["name"] for r in db.execute("SELECT * FROM floors WHERE project_id=?", (project_id,)).fetchall()}
    rooms = {r["id"]: r["name"] for r in db.execute(
        "SELECT r.id, r.name FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE f.project_id=?", (project_id,))}
    board_rows = db.execute(
        "SELECT * FROM distribution_boards WHERE project_id=? ORDER BY order_idx", (project_id,)
    ).fetchall()

    story = []
    if not board_rows:
        story.append(Paragraph("Noch keine Verteiler angelegt.", styles["BodyMuted"]))
        return story

    for i, row in enumerate(board_rows):
        if i > 0:
            story.append(Spacer(1, 6 * mm))
        serialized = _serialize_board(db, row)
        where = " / ".join(n for n in (floors.get(row["floor_id"], ""), rooms.get(row["room_id"], "")) if n)
        heading = row["name"] or "Verteiler"
        if where:
            heading += f" — {where}"
        heading_para = Paragraph(heading, styles["RoomHeading"])
        row_tables = [t for t in (
            _board_row_table(row_items, serialized["row_width_te"], styles)
            for row_items in serialized["rows"]
        ) if t]
        if row_tables:
            # Only the first row-table needs to be kept with the heading -
            # that's enough to stop the heading itself from ever being
            # stranded alone at the bottom of a page; later rows paginate
            # normally.
            story.append(KeepTogether([heading_para, row_tables[0]]))
            story.append(Spacer(1, 2 * mm))
            for table in row_tables[1:]:
                story.append(table)
                story.append(Spacer(1, 2 * mm))
        else:
            story.append(heading_para)

    return story


@router.get("/api/projects/{project_id}/export-distribution-boards.pdf")
def export_distribution_boards_pdf(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        styles = pdf_styles()
        story = company_header_block(company) + pdf_title_banner(
            f"Verteilerplanung — {project['name']}", "Schaltschrank-Layout je Geschoss",
        )
        story += build_distribution_boards_story(db, project_id, styles)

        return build_pdf_response(
            story,
            footer_left_text=f"Verteilerplanung · {project['name']}",
            filename=f"{project['name'].replace(' ', '_')}_verteilerplanung.pdf",
            doc_title=f"Verteilerplanung {project['name']}",
            footer_center_text=company_footer_line(company),
        )
