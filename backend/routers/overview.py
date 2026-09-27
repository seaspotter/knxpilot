"""
Overview tab ("Übersicht"): the project's landing sub-tab, a status
dashboard - one stat card per other sub-tab, summarizing floors/rooms,
group addresses, circuit assignment progress, planned devices, both
checklists' progress, open clarifications and manuals, each card jumping
straight to its sub-tab on click.

Rendered server-side with htmx (backend/templates/overview/tab.html);
this router only aggregates figures already computed elsewhere (get_circuits,
device_summary, build_ga_tree, ...) - no new business logic. The project
files ("Dateien") section on this same tab is project_files.py's own
domain and is fetched separately, the same way Setup -> Backup's file list
is nested into its own page.
"""
from fastapi import APIRouter, Request

from ..db import get_db
from ..ga_logic import build_ga_tree, get_central_functions_overview, get_circuits, get_room_functions_by_category
from ..templating import templates
from .checklists import CHECKLIST_SECTIONS, get_status_map
from .device_planning import device_summary
from .clarification_list import list_clarifications
from .manuals import list_project_manuals
from .building_structure import get_project_tree
from .distribution_boards import list_distribution_boards

router = APIRouter(tags=["overview"])


def _stat(subtab, title, body, warn=False):
    return {"subtab": subtab, "title": title, "body": body, "warn": warn}


def _overview_cards(project_id):
    tree = get_project_tree(project_id)
    rooms = [r for f in tree["floors"] for r in f["rooms"]]
    floor_count = len(tree["floors"])
    room_count = len(rooms)
    point_count = sum(len(r["points"]) for r in rooms)

    ga_tree = build_ga_tree(project_id)
    ga_count = sum(len(mid["subs"]) for m in ga_tree["main_groups"] for mid in m["middles"])

    with get_db() as db:
        circuits = get_circuits(db, project_id)
        status_map = get_status_map(db, project_id)
        fc_total = fc_checked = 0
        for room in rooms:
            for items in get_room_functions_by_category(db, room["id"]).values():
                for item in items:
                    fc_total += 1
                    if status_map.get(item["key"], {}).get("status") == "ok":
                        fc_checked += 1
        for _, items in get_central_functions_overview(db, project_id):
            for item in items:
                fc_total += 1
                if status_map.get(item["key"], {}).get("status") == "ok":
                    fc_checked += 1

    assigned_count = sum(1 for c in circuits if c["assignment"])
    total_circuits = len(circuits)

    device_total = sum(d["total"] for d in device_summary(project_id))
    board_count = len(list_distribution_boards(project_id))
    manuals = list_project_manuals(project_id)
    open_clarifications = sum(1 for c in list_clarifications(project_id) if c["status"] == "offen")

    handover_items = [f"handover:{slug}" for _, items in CHECKLIST_SECTIONS for slug, _ in items]
    handover_total = len(handover_items)
    handover_answered = sum(1 for key in handover_items if status_map.get(key, {}).get("status"))

    return [
        _stat("building-structure", "Gebäudestruktur", f"{floor_count} Geschosse · {room_count} Räume"),
        _stat("functions", "Funktionen",
              f"{point_count} Punkte definiert" if point_count else "Noch keine Punkte definiert"),
        _stat("group-addresses", "Gruppenadressen",
              f"{ga_count} Gruppenadressen" if ga_count else "Noch keine Gruppenadressen"),
        _stat("circuit-list", "Abgangsliste",
              f"{assigned_count} / {total_circuits} Abgänge zugeordnet" if total_circuits else "Noch keine Abgänge",
              warn=assigned_count < total_circuits),
        _stat("device-planning", "Geräteplanung",
              f"{device_total} Geräte geplant" if device_total else "Noch keine Geräte geplant"),
        _stat("distribution-boards", "Verteilerplanung",
              f"{board_count} Verteiler angelegt" if board_count else "Noch keine Verteiler angelegt"),
        _stat("specification", "Pflichtenheft", "Frühe Leistungsbeschreibung (PDF)"),
        _stat("function-checklist", "Funktionscheckliste",
              f"{fc_checked} / {fc_total} Funktionen getestet" if fc_total else "Noch keine Funktionen geplant"),
        _stat("handover-checklist", "Übergabe-Checkliste", f"{handover_answered} / {handover_total} Punkte beantwortet"),
        _stat("clarification-list", "Klärungsliste",
              f"{open_clarifications} offene Einträge" if open_clarifications else "Keine offenen Einträge",
              warn=open_clarifications > 0),
        _stat("manuals", "Handbücher",
              f"{sum(1 for m in manuals if m['file_id'])} / {len(manuals)} heruntergeladen"
              if manuals else "Keine Handbuch-Links hinterlegt"),
        _stat("documentation", "Dokumentation", "Abschlussdokumentation (PDF)"),
    ]


@router.get("/hx/projects/{project_id}/overview")
def hx_tab(request: Request, project_id: int):
    return templates.TemplateResponse(request, "overview/tab.html",
                                      {"cards": _overview_cards(project_id), "project_id": project_id})
