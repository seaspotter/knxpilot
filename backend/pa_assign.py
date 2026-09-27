"""
Physical-address (PA) auto-assign: fills in KNX individual/physical
addresses (e.g. "1.1.10") for actor instances (Abgangsliste), room devices,
and floor devices (Geräteplanung) that don't have one yet, following a
bucket convention: a fixed Systemgeräte block (0-5), then one Aktoren block
per indoor Geschoss, then one Sensoren/Bedienelemente block per indoor
Geschoss, then one Aussen block for anything on a Geschoss marked
Aussen/unbeheizt (Wetterstation devices first within it). Never touches an
address that's already set - same "only fill gaps" contract as the
existing circuit auto-assign (see routers/circuit_list.py).

Projects split into several KNX lines (knx_lines, see routers/lines.py)
run this bucketing once per line, each with its own "Bereich.Linie" prefix:
a device's line is its room's (or actuator's) own line, else its floor's,
else the project's first line. A line coupler is placed first among the
Systemgeräte so it gets the line's .0 address. Without any lines the whole
project is one line with the prefix typed in (default 1.1), as before.
"""
import math
import re

SYSTEMGERAET_GROUPS = {"Systemgerät", "Visualisierung/Logik"}
AKTOR_GROUP = "Aktor"
WETTERSTATION_GROUP = "Wetterstation"
SYSTEMGERAET_SLOTS = 6  # addresses 0-5

# The catalog has no explicit device role, so couplers and bus power supplies
# are recognised by their model/description (shown as such in the UI).
_COUPLER_RE = re.compile(r"koppler|coupler", re.IGNORECASE)
_POWER_SUPPLY_RE = re.compile(r"spannungsversorgung|knx.*power\s*supply", re.IGNORECASE)


def is_line_coupler(model, description):
    return bool(_COUPLER_RE.search(f"{model} {description}"))


def is_bus_power_supply(model, description):
    return bool(_POWER_SUPPLY_RE.search(f"{model} {description}"))


def _next_multiple_of_10(n):
    return ((n + 9) // 10) * 10


def _extract_suffix(address, prefix):
    """"1.1.51" with prefix "1.1" -> 51. None if it doesn't match the prefix
    or isn't a plain integer suffix (e.g. a manually-entered non-numeric
    address stays untouched and simply isn't tracked as "used")."""
    if not address.startswith(prefix + "."):
        return None
    try:
        return int(address[len(prefix) + 1:])
    except ValueError:
        return None


def project_lines(db, project_id):
    return db.execute(
        "SELECT * FROM knx_lines WHERE project_id=? ORDER BY area, line", (project_id,)
    ).fetchall()


def collect_devices(db, project_id):
    """Every device in the project with its effective line_id (None if the
    project/device has no line set) - shared by the PA assignment below and
    the per-line overview in routers/lines.py."""
    items = []
    for ai in db.execute(
        "SELECT ai.*, at.group_name, at.model, at.description, at.manufacturer, "
        "COALESCE(ai.line_id, f.line_id) AS eff_line_id FROM actor_instances ai "
        "JOIN actor_types at ON ai.actor_type_id = at.id LEFT JOIN floors f ON ai.floor_id = f.id "
        "WHERE ai.project_id=?",
        (project_id,),
    ).fetchall():
        items.append({
            "table": "actor_instances", "id": ai["id"], "floor_id": ai["floor_id"], "line_id": ai["eff_line_id"],
            "group_name": ai["group_name"], "address": ai["physical_address"],
            "model": ai["model"], "description": ai["description"], "manufacturer": ai["manufacturer"],
        })
    for rd in db.execute(
        "SELECT rd.*, r.floor_id as floor_id, at.group_name, at.model, at.description, at.manufacturer, "
        "COALESCE(r.line_id, f.line_id) AS eff_line_id FROM room_devices rd "
        "JOIN rooms r ON rd.room_id = r.id "
        "JOIN actor_types at ON rd.device_type_id = at.id "
        "JOIN floors f ON r.floor_id = f.id WHERE f.project_id=?",
        (project_id,),
    ).fetchall():
        items.append({
            "table": "room_devices", "id": rd["id"], "floor_id": rd["floor_id"], "line_id": rd["eff_line_id"],
            "group_name": rd["group_name"], "address": rd["physical_address"],
            "model": rd["model"], "description": rd["description"], "manufacturer": rd["manufacturer"],
        })
    for fd in db.execute(
        "SELECT fd.*, at.group_name, at.model, at.description, at.manufacturer, f.line_id AS eff_line_id "
        "FROM floor_devices fd "
        "JOIN actor_types at ON fd.device_type_id = at.id "
        "JOIN floors f ON fd.floor_id = f.id WHERE f.project_id=?",
        (project_id,),
    ).fetchall():
        items.append({
            "table": "floor_devices", "id": fd["id"], "floor_id": fd["floor_id"], "line_id": fd["eff_line_id"],
            "group_name": fd["group_name"], "address": fd["physical_address"],
            "model": fd["model"], "description": fd["description"], "manufacturer": fd["manufacturer"],
        })
    return items


def compute_pa_assignments(db, project_id, prefix):
    """Returns (assignments, skipped). `assignments` is a list of
    {"table": "actor_instances"|"room_devices"|"floor_devices", "id": int,
    "address": str} ready to write; `skipped` is a list of human-readable
    reasons (devices with no floor, or a full Systemgeräte block). `prefix`
    is only used for projects without KNX lines."""
    floors = db.execute(
        "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
    ).fetchall()
    items = collect_devices(db, project_id)
    all_addresses = [it["address"] for it in items if it["address"]]
    lines = project_lines(db, project_id)

    groups = []  # (prefix, items, floors that get address blocks)
    if not lines:
        groups.append((prefix, items, floors))
    else:
        default_line = lines[0]["id"]
        for line in lines:
            line_items = [it for it in items if (it["line_id"] or default_line) == line["id"]]
            # Only floors that actually have devices on this line reserve an
            # address block in it - otherwise line 1.2 (OG apartment) would
            # start its actuators at .20 because of an empty EG block.
            line_floor_ids = {it["floor_id"] for it in line_items}
            groups.append((f"{line['area']}.{line['line']}", line_items,
                           [f for f in floors if f["id"] in line_floor_ids]))

    assignments, skipped = [], []
    for group_prefix, group_items, group_floors in groups:
        used = {n for n in (_extract_suffix(a, group_prefix) for a in all_addresses) if n is not None}
        a, s = _assign_line(group_items, group_prefix, used, group_floors)
        assignments += a
        skipped += s
    return assignments, skipped


def _assign_line(items, prefix, used, floors):
    """The bucket convention for one line (see module docstring)."""
    indoor_floors = [f for f in floors if not f["is_outdoor"]]
    outdoor_floor_ids = {f["id"] for f in floors if f["is_outdoor"]}
    skipped = []
    candidates = []
    for it in items:
        # Systemgeräte don't need a Geschoss (typically central/DIN-rail
        # infrastructure, not tied to a room) - only Aktor/Sensor/Bedienelement
        # items are bucketed per floor, so only those require one below.
        if it["table"] == "actor_instances" and it["floor_id"] is None and it["group_name"] not in SYSTEMGERAET_GROUPS:
            if not it["address"]:
                skipped.append("Aktor ohne Geschoss (Abgangsliste)")
            continue
        candidates.append(it)

    systemgeraet = []
    aktoren_by_floor = {f["id"]: [] for f in indoor_floors}
    sensoren_by_floor = {f["id"]: [] for f in indoor_floors}
    aussen = []

    for item in candidates:
        if item["group_name"] in SYSTEMGERAET_GROUPS:
            # Always Systemgeräte, regardless of floor (even if placed on an
            # Aussen/unbeheizt floor - a line coupler doesn't become an
            # "outdoor device" just because of where it's physically mounted).
            systemgeraet.append(item)
        elif item["floor_id"] in outdoor_floor_ids:
            aussen.append(item)
        elif item["group_name"] == AKTOR_GROUP:
            if item["floor_id"] in aktoren_by_floor:
                aktoren_by_floor[item["floor_id"]].append(item)
            else:
                skipped.append("Aktor auf unbekanntem Geschoss")
        else:
            if item["floor_id"] in sensoren_by_floor:
                sensoren_by_floor[item["floor_id"]].append(item)
            else:
                skipped.append("Gerät auf unbekanntem Geschoss")

    # Line coupler first, so it gets the line's .0 address (KNX TP convention).
    systemgeraet.sort(key=lambda it: 0 if is_line_coupler(it["model"], it["description"]) else 1)
    # Wetterstation devices ordered first within the Aussen bucket.
    aussen.sort(key=lambda it: 0 if it["group_name"] == WETTERSTATION_GROUP else 1)

    assignments = []
    cursor = 0

    def assign_bucket(bucket_items, start):
        nonlocal cursor
        n = start
        for it in bucket_items:
            if it["address"]:
                continue  # never touch an address already set
            while n in used:
                n += 1
            assignments.append({"table": it["table"], "id": it["id"], "address": f"{prefix}.{n}"})
            used.add(n)
            n += 1
        decades = max(1, math.ceil(len(bucket_items) / 10))
        cursor = start + 10 * decades

    sg_n = 0
    for it in systemgeraet:
        if it["address"]:
            continue
        while sg_n in used and sg_n < SYSTEMGERAET_SLOTS:
            sg_n += 1
        if sg_n >= SYSTEMGERAET_SLOTS:
            skipped.append("Systemgerät (Block 0-5 voll)")
            continue
        assignments.append({"table": it["table"], "id": it["id"], "address": f"{prefix}.{sg_n}"})
        used.add(sg_n)
        sg_n += 1
    cursor = 10

    for floor in indoor_floors:
        assign_bucket(aktoren_by_floor[floor["id"]], _next_multiple_of_10(cursor))

    for floor in indoor_floors:
        assign_bucket(sensoren_by_floor[floor["id"]], _next_multiple_of_10(cursor))

    assign_bucket(aussen, _next_multiple_of_10(cursor))

    return assignments, skipped
