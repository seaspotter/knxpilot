"""
KNX lines (Gebäudestruktur sub-tab, optional): for the rare project split
into several TP lines - typically one per apartment, sometimes an extra
outdoor line - coupled via line couplers. A floor can be given a line
(default for its rooms, floor devices and actuators), and a room or an
actuator can override it. PA auto-assign then numbers each line on its own
(see pa_assign.py). Group addresses are unaffected - they're project-wide in
KNX; lines only change the physical topology.
"""
from fastapi import APIRouter, HTTPException

from ..db import get_db
from ..models import KnxLineIn, LineAssignIn
from ..pa_assign import collect_devices, is_bus_power_supply, is_line_coupler, project_lines

router = APIRouter(tags=["lines"])

MAX_DEVICES_PER_LINE = 64   # KNX TP line segment without line repeater
NEAR_LIMIT = 55


def _validate(line: KnxLineIn):
    if not (0 <= line.area <= 15 and 0 <= line.line <= 15):
        raise HTTPException(400, "Bereich und Linie müssen zwischen 0 und 15 liegen")


@router.get("/api/projects/{project_id}/lines")
def list_lines(project_id: int):
    """Every line with its device count and planning hints. Devices without
    an explicit line count towards the first line (same rule as PA
    auto-assign)."""
    with get_db() as db:
        lines = project_lines(db, project_id)
        if not lines:
            return []
        devices = collect_devices(db, project_id)
    default_line = lines[0]["id"]
    result = []
    for line in lines:
        mine = [d for d in devices if (d["line_id"] or default_line) == line["id"]]
        couplers = [d for d in mine if is_line_coupler(d["model"], d["description"])]
        supplies = [d for d in mine if is_bus_power_supply(d["model"], d["description"])]
        warnings = []
        if len(mine) > MAX_DEVICES_PER_LINE:
            warnings.append(f"{len(mine)} Geräte — mehr als {MAX_DEVICES_PER_LINE} pro Linie: Linienverstärker oder weitere Linie nötig")
        elif len(mine) >= NEAR_LIMIT:
            warnings.append(f"{len(mine)} von max. {MAX_DEVICES_PER_LINE} Geräten — kaum Reserve")
        if len(lines) > 1 and not couplers:
            warnings.append("Kein Linienkoppler geplant")
        if not supplies:
            warnings.append("Keine Busspannungsversorgung geplant")
        result.append({
            "id": line["id"], "area": line["area"], "line": line["line"], "name": line["name"],
            "address": f"{line['area']}.{line['line']}", "is_default": line["id"] == default_line,
            "device_count": len(mine), "coupler_count": len(couplers), "power_supply_count": len(supplies),
            "warnings": warnings,
        })
    return result


@router.post("/api/projects/{project_id}/lines")
def add_line(project_id: int, body: KnxLineIn):
    _validate(body)
    with get_db() as db:
        if db.execute("SELECT 1 FROM knx_lines WHERE project_id=? AND area=? AND line=?",
                      (project_id, body.area, body.line)).fetchone():
            raise HTTPException(400, f"Linie {body.area}.{body.line} gibt es in diesem Projekt schon")
        cur = db.execute("INSERT INTO knx_lines (project_id, area, line, name) VALUES (?, ?, ?, ?)",
                         (project_id, body.area, body.line, body.name.strip()))
        return {"id": cur.lastrowid}


@router.put("/api/lines/{line_id}")
def update_line(line_id: int, body: KnxLineIn):
    _validate(body)
    with get_db() as db:
        row = db.execute("SELECT project_id FROM knx_lines WHERE id=?", (line_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Linie nicht gefunden")
        clash = db.execute("SELECT 1 FROM knx_lines WHERE project_id=? AND area=? AND line=? AND id!=?",
                           (row["project_id"], body.area, body.line, line_id)).fetchone()
        if clash:
            raise HTTPException(400, f"Linie {body.area}.{body.line} gibt es in diesem Projekt schon")
        db.execute("UPDATE knx_lines SET area=?, line=?, name=? WHERE id=?",
                   (body.area, body.line, body.name.strip(), line_id))
    return {"ok": True}


@router.delete("/api/lines/{line_id}")
def delete_line(line_id: int):
    """Floors/rooms/actuators on this line fall back to inheriting (ON DELETE
    SET NULL). Physical addresses already assigned are left as they are."""
    with get_db() as db:
        db.execute("DELETE FROM knx_lines WHERE id=?", (line_id,))
    return {"ok": True}


def _assign(table, row_id, body, project_sql):
    with get_db() as db:
        row = db.execute(project_sql, (row_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Nicht gefunden")
        if body.line_id is not None and not db.execute(
            "SELECT 1 FROM knx_lines WHERE id=? AND project_id=?", (body.line_id, row["project_id"])
        ).fetchone():
            raise HTTPException(400, "Diese Linie gehört nicht zum Projekt")
        db.execute(f"UPDATE {table} SET line_id=? WHERE id=?", (body.line_id, row_id))
    return {"ok": True}


@router.put("/api/floors/{floor_id}/line")
def set_floor_line(floor_id: int, body: LineAssignIn):
    return _assign("floors", floor_id, body, "SELECT project_id FROM floors WHERE id=?")


@router.put("/api/rooms/{room_id}/line")
def set_room_line(room_id: int, body: LineAssignIn):
    return _assign("rooms", room_id, body,
                   "SELECT f.project_id FROM rooms r JOIN floors f ON r.floor_id = f.id WHERE r.id=?")


@router.put("/api/actor-instances/{ai_id}/line")
def set_actor_line(ai_id: int, body: LineAssignIn):
    return _assign("actor_instances", ai_id, body, "SELECT project_id FROM actor_instances WHERE id=?")
