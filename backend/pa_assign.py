"""
Physical-address (PA) auto-assign: fills in KNX individual/physical
addresses (e.g. "1.1.10") for actor instances (Abgangsliste) and room
devices (Geräteplanung) that don't have one yet, following a bucket
convention: a fixed Systemgeräte block (0-5), then one Aktoren block per
indoor Geschoss, then one Sensoren/Bedienelemente block per indoor
Geschoss, then one Aussen block for anything on a Geschoss marked
Aussen/unbeheizt (Wetterstation devices first within it). Never touches an
address that's already set - same "only fill gaps" contract as the
existing circuit auto-assign (see routers/abgangsliste.py).
"""
import math

SYSTEMGERAET_GROUPS = {"Systemgerät", "Visualisierung/Logik"}
AKTOR_GROUP = "Aktor"
WETTERSTATION_GROUP = "Wetterstation"
SYSTEMGERAET_SLOTS = 6  # addresses 0-5


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


def compute_pa_assignments(db, project_id, prefix):
    """Returns (assignments, skipped). `assignments` is a list of
    {"table": "actor_instances"|"room_devices", "id": int, "address": str}
    ready to write; `skipped` is a list of human-readable reasons (devices
    with no floor, or a full Systemgeräte block)."""
    floors = db.execute(
        "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
    ).fetchall()
    indoor_floors = [f for f in floors if not f["is_outdoor"]]
    outdoor_floor_ids = {f["id"] for f in floors if f["is_outdoor"]}

    items = []
    skipped = []

    for ai in db.execute(
        "SELECT ai.*, at.group_name FROM actor_instances ai "
        "JOIN actor_types at ON ai.actor_type_id = at.id WHERE ai.project_id=?",
        (project_id,),
    ).fetchall():
        # Systemgeräte don't need a Geschoss (typically central/DIN-rail
        # infrastructure, not tied to a room) - only Aktor/Sensor/Bedienelement
        # items are bucketed per floor, so only those require one below.
        if ai["floor_id"] is None and ai["group_name"] not in SYSTEMGERAET_GROUPS:
            if not ai["physical_address"]:
                skipped.append("Aktor ohne Geschoss (Abgangsliste)")
            continue
        items.append({
            "table": "actor_instances", "id": ai["id"], "floor_id": ai["floor_id"],
            "group_name": ai["group_name"], "address": ai["physical_address"],
        })

    for rd in db.execute(
        "SELECT rd.*, r.floor_id as floor_id, at.group_name FROM room_devices rd "
        "JOIN rooms r ON rd.room_id = r.id "
        "JOIN actor_types at ON rd.device_type_id = at.id "
        "JOIN floors f ON r.floor_id = f.id WHERE f.project_id=?",
        (project_id,),
    ).fetchall():
        items.append({
            "table": "room_devices", "id": rd["id"], "floor_id": rd["floor_id"],
            "group_name": rd["group_name"], "address": rd["physical_address"],
        })

    used = set()
    for row in db.execute(
        "SELECT physical_address FROM actor_instances WHERE project_id=? AND physical_address != ''",
        (project_id,),
    ).fetchall():
        n = _extract_suffix(row["physical_address"], prefix)
        if n is not None:
            used.add(n)
    for row in db.execute(
        "SELECT rd.physical_address FROM room_devices rd JOIN rooms r ON rd.room_id=r.id "
        "JOIN floors f ON r.floor_id=f.id WHERE f.project_id=? AND rd.physical_address != ''",
        (project_id,),
    ).fetchall():
        n = _extract_suffix(row["physical_address"], prefix)
        if n is not None:
            used.add(n)

    systemgeraet = []
    aktoren_by_floor = {f["id"]: [] for f in indoor_floors}
    sensoren_by_floor = {f["id"]: [] for f in indoor_floors}
    aussen = []

    for item in items:
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
