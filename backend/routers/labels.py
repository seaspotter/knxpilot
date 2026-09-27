"""
Labels tab: prints a label sheet for cabinet/terminal labelling, one label
per actor instance or per channel/circuit - see ../labels.py for the sheet
layout registry (LABEL_FORMATS) and the PDF rendering itself
(render_label_sheet), kept there as a shared helper module since it's pure
print-layout logic with no tab-specific state.

Rendered server-side with htmx (see DEVELOPMENT.md "htmx tabs"): the tab is
just a form (no persisted state of its own), so there's a single /hx/...
endpoint that renders it - the label-position grid and the PDF download
itself stay small vanilla JS (frontend/js/labels.js), there being nothing
here worth a server round-trip for.
"""
from fastapi import APIRouter, HTTPException, Request

from ..db import get_db
from ..ga_logic import get_circuits
from ..labels import LABEL_FORMATS, render_label_sheet
from ..templating import templates
from ..utils import join_parts, channel_letters

router = APIRouter(tags=["labels"])


@router.get("/api/projects/{project_id}/export-labels.pdf")
def export_labels_pdf(project_id: int, format: str = "l6037", source: str = "actors", start: int = 1, debug: bool = False):
    """
    Label sheet export (see ../labels.py for the format registry). Two
    content sources: "actors" - one label per actor instance
    (physical_address + location_label, matching how this field is
    actually used in practice: the cabinet position like "1.1.2" plus a
    free-text description); or "channels" - one label per channel/circuit
    (physical_address.letter + the assigned function, or RESERVE if
    unassigned).
    """
    if format not in LABEL_FORMATS:
        raise HTTPException(400, f"Unknown label format '{format}'")
    if source not in ("actors", "channels"):
        raise HTTPException(400, "source must be 'actors' or 'channels'")

    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        actor_instances = db.execute(
            "SELECT ai.*, at.channel_type as ct, at.channel_count as cc, "
            "at.manufacturer as at_manufacturer, at.model as at_model "
            "FROM actor_instances ai JOIN actor_types at ON ai.actor_type_id = at.id "
            "WHERE ai.project_id=? ORDER BY ai.order_idx",
            (project_id,),
        ).fetchall()

        items = []
        if source == "actors":
            for ai in actor_instances:
                line1 = ai["physical_address"] or "-"
                line2 = ai["location_label"] or join_parts(ai["at_manufacturer"], ai["at_model"])
                items.append((line1, line2))
        else:
            circuits = get_circuits(db, project_id)
            by_room_point = {(c["room_point_id"], c["channel_seq"]): c for c in circuits}
            assignments = db.execute(
                "SELECT * FROM channel_assignments WHERE project_id=?", (project_id,)
            ).fetchall()
            for ai in actor_instances:
                by_letter = {}
                for a in assignments:
                    if a["actor_instance_id"] == ai["id"]:
                        circuit = by_room_point.get((a["room_point_id"], a["channel_seq"]))
                        by_letter[a["channel_letter"]] = circuit["function_name"] if circuit else "?"
                for letter in channel_letters(ai["cc"]):
                    line1 = f"{ai['physical_address']}.{letter}" if ai["physical_address"] else letter
                    line2 = by_letter.get(letter, "RESERVE")
                    items.append((line1, line2))

        if not items:
            raise HTTPException(400, "Keine Aktoren in diesem Projekt - zuerst in der Abgangsliste anlegen")

        return render_label_sheet(
            items,
            filename=f"{project['name'].replace(' ', '_')}_etiketten.pdf",
            format=format,
            start=start,
            debug=debug,
        )


# --------------------------------------------------------------------------
# htmx fragment (backend/templates/labels/)
# --------------------------------------------------------------------------
@router.get("/hx/projects/{project_id}/labels")
def hx_tab(request: Request, project_id: int):
    return templates.TemplateResponse(request, "labels/tab.html", {
        "project_id": project_id, "formats": LABEL_FORMATS,
    })
