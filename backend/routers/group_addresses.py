"""
Group addresses tab ("Gruppenadressen" sub-tab): the GA tree preview, the
ETS6 CSV export and what changed since the last export.

Rendered server-side with htmx (see DEVELOPMENT.md "htmx tabs"): the
/hx/... endpoints below return HTML fragments from
backend/templates/group_addresses/. The JSON endpoints stay for the CSV/PDF
exports (email.py) and the tests.
"""
import csv
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..db import get_db
from ..ga_logic import build_ga_tree, flatten_ga_tree, is_function_row
from ..templating import client_zone, templates
from ..utils import content_disposition

router = APIRouter(tags=["group-addresses"])


# --------------------------------------------------------------------------
# JSON API / CSV export
# --------------------------------------------------------------------------
@router.get("/api/projects/{project_id}/preview")
def preview_ga(project_id: int):
    return build_ga_tree(project_id)


def _save_ga_snapshot(project_id, tree):
    with get_db() as db:
        db.execute(
            "INSERT INTO ga_export_snapshots (project_id, exported_at, data) VALUES (?, ?, ?) "
            "ON CONFLICT(project_id) DO UPDATE SET exported_at=excluded.exported_at, data=excluded.data",
            (project_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
             json.dumps(flatten_ga_tree(tree), ensure_ascii=False)),
        )


def _address_key(address):
    return tuple(-1 if part == "-" else int(part) for part in address.split("/"))


def _ga_changes(project_id):
    """What changed in the group addresses since the last ETS export - i.e.
    what still has to be done in ETS.

    Adding or removing a function shifts every later address in its block,
    so real functions are matched by name first: one that now sits on a
    different address is "moved" (in ETS: change that group address's
    address, which keeps its links to devices - not delete + re-create).
    Moves are listed from the highest target address down, the order that
    avoids address collisions in ETS. With the moves applied, the rest is
    compared by address: "added" (create), "changed" (same address, new name
    or DPT - e.g. a renamed room, or a "res" slot now used by a function)
    and "removed" (delete)."""
    current = flatten_ga_tree(build_ga_tree(project_id))
    with get_db() as db:
        snap = db.execute("SELECT * FROM ga_export_snapshots WHERE project_id=?", (project_id,)).fetchone()
    if not snap:
        return {"exported_at": None, "total": len(current)}
    before = json.loads(snap["data"])

    def unique_functions(rows):
        names = [r["name"] for r in rows if is_function_row(r)]
        return {r["name"]: r for r in rows if is_function_row(r) and names.count(r["name"]) == 1}
    before_fn, now_fn = unique_functions(before), unique_functions(current)
    moved = [
        {"name": n, "old_address": before_fn[n]["address"], "address": now_fn[n]["address"],
         "old_dpt": before_fn[n]["dpt"], "dpt": now_fn[n]["dpt"]}
        for n in now_fn if n in before_fn and before_fn[n]["address"] != now_fn[n]["address"]
    ]

    # ETS state once the moves are done: moved functions leave their old
    # address and take their new one (anything that sat there has to go).
    state = {r["address"]: r for r in before}
    displaced = []
    for m in moved:
        state.pop(m["old_address"], None)
    for m in moved:
        if m["address"] in state:
            displaced.append(state[m["address"]])
        state[m["address"]] = {"address": m["address"], "name": m["name"], "dpt": m["old_dpt"]}

    now = {r["address"]: r for r in current}
    added = [now[a] for a in now if a not in state]
    removed = [state[a] for a in state if a not in now] + displaced
    changed = [
        {"address": a, "old_name": state[a]["name"], "name": now[a]["name"], "old_dpt": state[a]["dpt"], "dpt": now[a]["dpt"]}
        for a in now if a in state and (state[a]["name"], state[a]["dpt"]) != (now[a]["name"], now[a]["dpt"])
    ]
    by_addr = lambda rows: sorted(rows, key=lambda r: _address_key(r["address"]))
    return {
        "exported_at": snap["exported_at"], "total": len(current),
        "moved": sorted(moved, key=lambda r: _address_key(r["address"]), reverse=True),
        "added": by_addr(added), "changed": by_addr(changed), "removed": by_addr(removed),
    }


@router.get("/api/projects/{project_id}/ga-changes")
def ga_changes(project_id: int):
    return _ga_changes(project_id)


@router.post("/api/projects/{project_id}/ga-snapshot")
def mark_ga_exported(project_id: int):
    """"Aktuellen Stand als in ETS übernommen markieren" - sets the baseline
    without downloading (e.g. the ETS project was already brought up to date
    by hand, or for projects exported before snapshots existed)."""
    _save_ga_snapshot(project_id, build_ga_tree(project_id))
    return {"ok": True}


@router.get("/api/projects/{project_id}/export.csv")
def export_csv(project_id: int):
    data = build_ga_tree(project_id)
    # This download is "the ETS export" - remember it as the baseline for
    # the changes view above.
    _save_ga_snapshot(project_id, data)

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t", quotechar='"', quoting=csv.QUOTE_ALL)

    writer.writerow(
        ["Main", "Middle", "Sub", "Address", "Central", "Unfiltered", "Description", "DatapointType", "Security"]
    )

    for main in data["main_groups"]:
        writer.writerow([main["name"], "", "", f"{main['main']}/-/-", "", "", "", "", "Auto"])
        for middle in main["middles"]:
            writer.writerow(["", middle["name"], "", f"{main['main']}/{middle['middle']}/-", "", "", "", "", "Auto"])
            for sub in middle["subs"]:
                writer.writerow(
                    [
                        "", "", sub["name"],
                        f"{main['main']}/{middle['middle']}/{sub['sub']}",
                        "", "", "", sub["dpt"], "Auto",
                    ]
                )

    buf.seek(0)
    filename = f"{data['project_name'].replace(' ', '_')}_group_addresses.csv"
    return StreamingResponse(
        iter([buf.getvalue().encode("iso-8859-1", errors="replace")]),
        media_type="text/csv",
        headers={"Content-Disposition": content_disposition(filename)},
    )


# --------------------------------------------------------------------------
# htmx fragments (backend/templates/group_addresses/)
# --------------------------------------------------------------------------
def _changes_context(request, project_id):
    changes = _ga_changes(project_id)
    exported_at_local = None
    if changes["exported_at"]:
        dt = datetime.fromisoformat(changes["exported_at"]).astimezone(client_zone(request))
        exported_at_local = dt.strftime("%d.%m.%Y %H:%M")
    return {"project_id": project_id, "changes": changes, "exported_at_local": exported_at_local}


def _changes(request, project_id):
    return templates.TemplateResponse(request, "group_addresses/_changes.html", _changes_context(request, project_id))


@router.get("/hx/projects/{project_id}/group-addresses")
def hx_tab(request: Request, project_id: int):
    with get_db() as db:
        if not db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
            raise HTTPException(404, "Project not found")
    return templates.TemplateResponse(request, "group_addresses/tab.html", {
        **_changes_context(request, project_id), "preview": build_ga_tree(project_id),
    })


@router.get("/hx/projects/{project_id}/group-addresses/changes")
def hx_changes(request: Request, project_id: int):
    return _changes(request, project_id)


@router.post("/hx/projects/{project_id}/group-addresses/snapshot")
def hx_mark_exported(request: Request, project_id: int):
    _save_ga_snapshot(project_id, build_ga_tree(project_id))
    response = _changes(request, project_id)
    response.headers["HX-Trigger"] = json.dumps({"show-toast": {"message": "Als in ETS übernommen markiert", "level": "success"}})
    return response
