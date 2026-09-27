"""
Labels tab: prints a label sheet for cabinet/terminal labelling, one label
per physical device with a physical address (actors from the Abgangsliste,
plus room/floor devices from Geräteplanung) - see ../labels.py for the sheet
layout registry (LABEL_FORMATS) and the PDF rendering itself
(render_label_sheet), kept there as a shared helper module since it's pure
print-layout logic with no tab-specific state.

Only used to have a "channels" source too (one label per channel/circuit
instead of per actor) - dropped since nobody used it and it's the same
per-actor loop plus a channel_assignments join, easy to bring back from
git history if ever needed.

Rendered server-side with htmx (see DEVELOPMENT.md "htmx tabs"): the tab is
just a form (no persisted state of its own), so there's a single /hx/...
endpoint that renders it - the label-position grid and the PDF download
itself stay small vanilla JS (frontend/js/labels.js), there being nothing
here worth a server round-trip for.
"""
from fastapi import APIRouter, HTTPException, Request

from ..db import get_db
from ..labels import LABEL_FORMATS, render_label_sheet
from ..templating import templates

router = APIRouter(tags=["labels"])


def _pa_sort_key(physical_address):
    """Sorts "1.1.2" before "1.1.10" (plain string sort would put "10"
    before "2") - falls back to the raw string for anything non-numeric."""
    parts = physical_address.split(".")
    try:
        return (0, tuple(int(p) for p in parts))
    except ValueError:
        return (1, physical_address)


@router.get("/api/projects/{project_id}/export-labels.pdf")
def export_labels_pdf(project_id: int, format: str = "l6037", start: int = 1, debug: bool = False):
    """One label per device with a physical address, project-wide - actor
    instances (Abgangsliste) plus room/floor devices (Geräteplanung), sorted
    by physical address. The second line is just where the device is
    (an actor's location_label, or the room/floor name for a device from
    Geräteplanung) - deliberately no device type/model, so the label stays
    short and matches how these are actually read on-site: "which cabinet
    position is this room's sensor". A room/floor device's quantity is
    always split into separate rows with their own address at creation time
    (see routers/device_planning.py's add_room_device), so this never needs
    to duplicate a label for a shared address."""
    if format not in LABEL_FORMATS:
        raise HTTPException(400, f"Unknown label format '{format}'")

    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        entries = []  # (physical_address, line2)

        actor_instances = db.execute(
            "SELECT physical_address, location_label FROM actor_instances "
            "WHERE project_id=? AND physical_address != ''",
            (project_id,),
        ).fetchall()
        for ai in actor_instances:
            entries.append((ai["physical_address"], ai["location_label"] or ""))

        room_devices = db.execute(
            "SELECT rd.physical_address, r.name as room_name "
            "FROM room_devices rd JOIN rooms r ON rd.room_id = r.id "
            "JOIN floors f ON r.floor_id = f.id "
            "WHERE f.project_id=? AND rd.physical_address != ''",
            (project_id,),
        ).fetchall()
        for rd in room_devices:
            entries.append((rd["physical_address"], rd["room_name"]))

        floor_devices = db.execute(
            "SELECT fd.physical_address, f.name as floor_name "
            "FROM floor_devices fd JOIN floors f ON fd.floor_id = f.id "
            "WHERE f.project_id=? AND fd.physical_address != ''",
            (project_id,),
        ).fetchall()
        for fd in floor_devices:
            entries.append((fd["physical_address"], fd["floor_name"]))

        if not entries:
            raise HTTPException(400, "Keine Geräte mit physikalischer Adresse in diesem Projekt")

        entries.sort(key=lambda e: _pa_sort_key(e[0]))
        items = [(pa, line2) for pa, line2 in entries]

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
