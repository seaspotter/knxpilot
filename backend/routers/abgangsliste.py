"""
Abgangsliste tab: physical actuator instances placed in a project, the
circuits (physical outputs) that need wiring to them, channel assignment
(manual + auto), and the CSV/PDF wiring-list exports.
"""
import csv
import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, PageBreak
from reportlab.lib.units import mm

from ..db import get_db
from ..ga_logic import get_circuits
from ..labels import LABEL_FORMATS, render_label_sheet
from ..models import ActorInstanceIn, ActorInstanceEditIn, ChannelAssignIn, PhysicalAddressAssignIn
from ..pa_assign import compute_pa_assignments
from ..pdf_design import pdf_styles, pdf_title_banner, pdf_table_style, build_pdf_response, company_header_block, company_footer_line, PDF_MUTED_COLOR
from ..utils import join_parts, channel_letters

router = APIRouter(tags=["abgangsliste"])


# --------------------------------------------------------------------------
# Actor Instances (physical devices placed in a project)
# --------------------------------------------------------------------------
@router.get("/api/projects/{project_id}/actor-instances")
def list_actor_instances(project_id: int):
    with get_db() as db:
        actor_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM actor_types").fetchall()}
        floors = {r["id"]: r["name"] for r in db.execute("SELECT * FROM floors WHERE project_id=?", (project_id,)).fetchall()}
        rows = db.execute(
            "SELECT * FROM actor_instances WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall()

        # Build (actor_instance_id, channel_letter) -> function name, reusing the same
        # naming logic get_circuits already uses, so the map always matches the CSV/PDF exports.
        circuits = get_circuits(db, project_id)
        function_by_channel = {}
        for c in circuits:
            if c["assignment"]:
                key = (c["assignment"]["actor_instance_id"], c["assignment"]["channel_letter"])
                function_by_channel[key] = c["function_name"]

        result = []
        for r in rows:
            at = actor_types.get(r["actor_type_id"], {})
            # .get(..., 0) only helps if the key is missing - actor_types always
            # has a channel_count column, just NULL for non-Aktor groups, so the
            # default never kicked in and channel_letters(None) below crashed.
            channel_count = at.get("channel_count") or 0
            used = db.execute(
                "SELECT channel_letter FROM channel_assignments WHERE actor_instance_id=?", (r["id"],)
            ).fetchall()
            used_letters = {u["channel_letter"] for u in used}
            channel_map = [
                {"letter": letter, "function": function_by_channel.get((r["id"], letter))}
                for letter in channel_letters(channel_count)
            ]
            result.append(
                {
                    "id": r["id"], "actor_type_id": r["actor_type_id"],
                    "actor_type_name": join_parts(at.get("manufacturer", ""), at.get("model", "")) or "?",
                    "channel_type": at.get("channel_type", ""), "channel_count": channel_count,
                    "floor_id": r["floor_id"], "floor_name": floors.get(r["floor_id"], ""),
                    "location_label": r["location_label"], "physical_address": r["physical_address"],
                    "channels_used": len(used_letters), "channels_free": channel_count - len(used_letters),
                    "channel_map": channel_map,
                }
            )
        return result


@router.post("/api/projects/{project_id}/actor-instances")
def add_actor_instance(project_id: int, ai: ActorInstanceIn):
    with get_db() as db:
        (count,) = db.execute(
            "SELECT COUNT(*) FROM actor_instances WHERE project_id=?", (project_id,)
        ).fetchone()
        cur = db.execute(
            "INSERT INTO actor_instances (project_id, actor_type_id, floor_id, location_label, physical_address, order_idx) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, ai.actor_type_id, ai.floor_id, ai.location_label, ai.physical_address, count),
        )
        return {"id": cur.lastrowid}


@router.put("/api/actor-instances/{ai_id}")
def update_actor_instance(ai_id: int, ai: ActorInstanceEditIn):
    with get_db() as db:
        db.execute(
            "UPDATE actor_instances SET floor_id=?, location_label=?, physical_address=? WHERE id=?",
            (ai.floor_id, ai.location_label, ai.physical_address, ai_id),
        )
    return {"ok": True}


@router.delete("/api/actor-instances/{ai_id}")
def delete_actor_instance(ai_id: int):
    with get_db() as db:
        db.execute("DELETE FROM actor_instances WHERE id=?", (ai_id,))
    return {"ok": True}


@router.post("/api/projects/{project_id}/assign-physical-addresses")
def assign_physical_addresses(project_id: int, body: PhysicalAddressAssignIn):
    """Fills in KNX physical addresses for every actor instance (Abgangsliste)
    and room/floor device (Geräteplanung) in the project that doesn't have one
    yet - see pa_assign.py for the bucket/spacing convention. Never touches an
    address already set; devices with no Geschoss are skipped and reported."""
    prefix = body.prefix.strip() or "1.1"
    with get_db() as db:
        assignments, skipped = compute_pa_assignments(db, project_id, prefix)
        for a in assignments:
            # a["table"] only ever comes from pa_assign.py's own hardcoded
            # literals ("actor_instances" / "room_devices" / "floor_devices"),
            # never user input.
            db.execute(f"UPDATE {a['table']} SET physical_address=? WHERE id=?", (a["address"], a["id"]))
    return {"assigned": len(assignments), "skipped": skipped}


# --------------------------------------------------------------------------
# Circuits (physical outputs) + channel assignment
# --------------------------------------------------------------------------
@router.get("/api/projects/{project_id}/circuits")
def list_circuits(project_id: int):
    with get_db() as db:
        return get_circuits(db, project_id)


@router.get("/api/projects/{project_id}/channel-summary")
def channel_summary(project_id: int):
    """Per floor, per channel type: how many circuits are needed in total, and how many
    are already assigned - to help pick the right actuator size before wiring anything."""
    with get_db() as db:
        circuits = get_circuits(db, project_id)
        summary = {}
        for c in circuits:
            key = (c["floor_id"], c["floor_name"], c["channel_type"])
            entry = summary.setdefault(key, {"needed": 0, "assigned": 0})
            entry["needed"] += 1
            if c["assignment"]:
                entry["assigned"] += 1
        result = [
            {
                "floor_id": floor_id, "floor_name": floor_name, "channel_type": channel_type,
                "needed": v["needed"], "assigned": v["assigned"], "open": v["needed"] - v["assigned"],
            }
            for (floor_id, floor_name, channel_type), v in summary.items()
        ]
        result.sort(key=lambda r: (r["floor_name"], r["channel_type"]))
        return result


@router.post("/api/projects/{project_id}/circuits/assign")
def assign_circuit(project_id: int, a: ChannelAssignIn):
    with get_db() as db:
        # Free up this circuit's previous assignment, if any (moving it to a new channel).
        db.execute(
            "DELETE FROM channel_assignments WHERE room_point_id=? AND channel_seq=?",
            (a.room_point_id, a.channel_seq),
        )
        taken = db.execute(
            "SELECT 1 FROM channel_assignments WHERE actor_instance_id=? AND channel_letter=?",
            (a.actor_instance_id, a.channel_letter),
        ).fetchone()
        if taken:
            raise HTTPException(400, f"Channel {a.channel_letter} is already assigned to something else")
        db.execute(
            "INSERT INTO channel_assignments (project_id, room_point_id, channel_seq, actor_instance_id, channel_letter) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, a.room_point_id, a.channel_seq, a.actor_instance_id, a.channel_letter),
        )
    return {"ok": True}


@router.delete("/api/projects/{project_id}/circuits/{room_point_id}/{channel_seq}")
def unassign_circuit(project_id: int, room_point_id: int, channel_seq: int):
    with get_db() as db:
        db.execute(
            "DELETE FROM channel_assignments WHERE room_point_id=? AND channel_seq=?",
            (room_point_id, channel_seq),
        )
    return {"ok": True}


@router.post("/api/projects/{project_id}/circuits/auto-assign")
def auto_assign_circuits(project_id: int):
    """Fills every unassigned circuit into the first free matching-type channel available
    on an actuator on THE SAME FLOOR as the circuit (never mixes floors automatically -
    e.g. an EG circuit will never be auto-assigned to an OG cabinet, even if EG is full).
    Actuators with no floor set are not used by auto-assign either, since there's no floor
    to match against; assign those manually instead. Does not touch circuits already assigned.

    Rollo/Jalousie circuits get a further preference: when 2+ unassigned circuits from
    the SAME ROOM land on the same actuator, they're placed on an aligned channel pair
    (A+B, C+D, E+F, G+H) rather than whatever two channels happen to be next free - many
    shading actuators wire channels in fixed pairs sharing a common input/reference, so
    two blinds in one room (e.g. two windows) should share a pair for correct wiring, not
    just consume the next free letters in document order."""
    with get_db() as db:
        circuits = get_circuits(db, project_id)
        actor_instances = db.execute(
            "SELECT ai.*, at.channel_type as ct, at.channel_count as cc "
            "FROM actor_instances ai JOIN actor_types at ON ai.actor_type_id = at.id "
            "WHERE ai.project_id=? ORDER BY ai.order_idx",
            (project_id,),
        ).fetchall()

        used_by_actor = {}
        for row in db.execute(
            "SELECT actor_instance_id, channel_letter FROM channel_assignments WHERE project_id=?", (project_id,)
        ).fetchall():
            used_by_actor.setdefault(row["actor_instance_id"], set()).add(row["channel_letter"])

        assigned_count = 0
        unassigned = []

        def assign(circuit, ai, letter):
            nonlocal assigned_count
            db.execute(
                "INSERT INTO channel_assignments "
                "(project_id, room_point_id, channel_seq, actor_instance_id, channel_letter) "
                "VALUES (?, ?, ?, ?, ?)",
                (project_id, circuit["room_point_id"], circuit["channel_seq"], ai["id"], letter),
            )
            used_by_actor.setdefault(ai["id"], set()).add(letter)
            assigned_count += 1

        def candidates_for(circuit):
            # never auto-assign across floors, even if a same-type actuator elsewhere has room
            return [ai for ai in actor_instances if ai["ct"] == circuit["channel_type"] and ai["floor_id"] == circuit["floor_id"]]

        def first_free_channel(ai):
            used = used_by_actor.setdefault(ai["id"], set())
            for letter in channel_letters(ai["cc"]):
                if letter not in used:
                    return letter
            return None

        def free_aligned_pair(ai):
            letters = channel_letters(ai["cc"])
            used = used_by_actor.setdefault(ai["id"], set())
            for i in range(0, len(letters) - 1, 2):
                a, b = letters[i], letters[i + 1]
                if a not in used and b not in used:
                    return a, b
            return None

        def place_single(circuit):
            for ai in candidates_for(circuit):
                letter = first_free_channel(ai)
                if letter:
                    assign(circuit, ai, letter)
                    return True
            return False

        still_unassigned = [c for c in circuits if not c["assignment"]]
        rollo_circuits = [c for c in still_unassigned if c["channel_type"] == "Rollo"]
        other_circuits = [c for c in still_unassigned if c["channel_type"] != "Rollo"]

        rooms = {}
        for c in rollo_circuits:
            rooms.setdefault((c["floor_id"], c["room_id"]), []).append(c)

        for group in rooms.values():
            i = 0
            while i < len(group):
                circuit = group[i]
                placed = False
                if i + 1 < len(group):
                    next_circuit = group[i + 1]
                    for ai in candidates_for(circuit):
                        pair = free_aligned_pair(ai)
                        if pair:
                            assign(circuit, ai, pair[0])
                            assign(next_circuit, ai, pair[1])
                            placed = True
                            i += 2
                            break
                if not placed:
                    if place_single(circuit):
                        placed = True
                    i += 1
                if not placed:
                    unassigned.append(f"{circuit['floor_name']} / {circuit['function_name']} ({circuit['channel_type']})")

        for circuit in other_circuits:
            if not place_single(circuit):
                unassigned.append(f"{circuit['floor_name']} / {circuit['function_name']} ({circuit['channel_type']})")

        return {"assigned": assigned_count, "unassigned": unassigned}


# --------------------------------------------------------------------------
# Exports
# --------------------------------------------------------------------------
@router.get("/api/projects/{project_id}/export-abgangsliste.csv")
def export_abgangsliste(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        circuits = get_circuits(db, project_id)
        by_room_point = {(c["room_point_id"], c["channel_seq"]): c for c in circuits}

        actor_instances = db.execute(
            "SELECT ai.*, at.channel_type as ct, at.channel_count as cc, "
            "at.manufacturer as at_manufacturer, at.model as at_model "
            "FROM actor_instances ai JOIN actor_types at ON ai.actor_type_id = at.id "
            "WHERE ai.project_id=? ORDER BY ai.order_idx",
            (project_id,),
        ).fetchall()
        floors = {r["id"]: r["name"] for r in db.execute("SELECT * FROM floors WHERE project_id=?", (project_id,)).fetchall()}
        assignments = db.execute(
            "SELECT * FROM channel_assignments WHERE project_id=?", (project_id,)
        ).fetchall()

        buf = io.StringIO()
        writer = csv.writer(buf, delimiter="\t", quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(["Geschoss", "Raum/UV", "Aktor", "Physikalische Adr.", "Kanal", "Funktion"])

        for ai in actor_instances:
            by_letter = {}
            for a in assignments:
                if a["actor_instance_id"] == ai["id"]:
                    circuit = by_room_point.get((a["room_point_id"], a["channel_seq"]))
                    by_letter[a["channel_letter"]] = circuit["function_name"] if circuit else "?"

            actor_display = join_parts(ai["at_manufacturer"], ai["at_model"])
            for i, letter in enumerate(channel_letters(ai["cc"])):
                first_row = i == 0
                writer.writerow(
                    [
                        floors.get(ai["floor_id"], "") if first_row else "",
                        ai["location_label"] if first_row else "",
                        actor_display if first_row else "",
                        ai["physical_address"] if first_row else "",
                        letter,
                        by_letter.get(letter, "RESERVE"),
                    ]
                )

        buf.seek(0)
        filename = f"{project['name'].replace(' ', '_')}_abgangsliste.csv"
        return StreamingResponse(
            iter([buf.getvalue().encode("iso-8859-1", errors="replace")]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


def build_abgangsliste_story(db, project_id, styles, page_break_between_floors=True):
    """The per-floor/per-actuator/per-channel content of the Abgangsliste, as a
    list of flowables - factored out of export_abgangsliste_pdf() so the
    Pflichtenheft export can optionally include the same content (see
    pflichtenheft.py's pflichtenheft_include_abgangsliste toggle) without
    duplicating this query/rendering logic."""
    circuits = get_circuits(db, project_id)
    by_room_point = {(c["room_point_id"], c["channel_seq"]): c for c in circuits}

    actor_instances = db.execute(
        "SELECT ai.*, at.channel_type as ct, at.channel_count as cc, "
        "at.manufacturer as at_manufacturer, at.model as at_model "
        "FROM actor_instances ai JOIN actor_types at ON ai.actor_type_id = at.id "
        "WHERE ai.project_id=? ORDER BY ai.order_idx",
        (project_id,),
    ).fetchall()
    floors_rows = db.execute(
        "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
    ).fetchall()
    floor_names = {r["id"]: r["name"] for r in floors_rows}
    floor_order = {r["id"]: r["order_idx"] for r in floors_rows}
    assignments = db.execute(
        "SELECT * FROM channel_assignments WHERE project_id=?", (project_id,)
    ).fetchall()

    story = []
    if not actor_instances:
        story.append(Paragraph("Noch keine Aktoren in diesem Projekt angelegt.", styles["BodyMuted"]))
        return story

    # Group actuators by floor, in floor order, "no floor" last.
    by_floor = {}
    for ai in actor_instances:
        by_floor.setdefault(ai["floor_id"], []).append(ai)
    floor_ids_sorted = sorted(by_floor.keys(), key=lambda fid: (fid is None, floor_order.get(fid, 999)))

    first_floor = True
    for floor_id in floor_ids_sorted:
        if not first_floor and page_break_between_floors:
            story.append(PageBreak())
        first_floor = False

        floor_label = floor_names.get(floor_id, "Ohne Geschoss")
        floor_heading = Paragraph(floor_label, styles["SectionHeading"])

        for idx, ai in enumerate(by_floor[floor_id]):
            actor_display = join_parts(ai["at_manufacturer"], ai["at_model"]) or "?"
            subtitle_parts = [actor_display]
            if ai["location_label"]:
                subtitle_parts.append(ai["location_label"])
            if ai["physical_address"]:
                subtitle_parts.append(ai["physical_address"])
            actor_heading = Paragraph(" · ".join(subtitle_parts), styles["RoomHeading"])

            by_letter = {}
            for a in assignments:
                if a["actor_instance_id"] == ai["id"]:
                    circuit = by_room_point.get((a["room_point_id"], a["channel_seq"]))
                    by_letter[a["channel_letter"]] = circuit["function_name"] if circuit else "?"

            table_data = [["Kanal", "Funktion"]]
            row_styles = []
            for i, letter in enumerate(channel_letters(ai["cc"])):
                function = by_letter.get(letter, "RESERVE")
                table_data.append([letter, function])
                if function == "RESERVE":
                    row_styles.append(("TEXTCOLOR", (0, i + 1), (-1, i + 1), PDF_MUTED_COLOR))
                    row_styles.append(("FONTNAME", (0, i + 1), (-1, i + 1), "Helvetica-Oblique"))

            table = Table(table_data, colWidths=[25 * mm, 130 * mm])
            table.setStyle(pdf_table_style(row_styles))

            # Keep the floor heading with the first actuator's own heading +
            # channel table (not just the floor heading alone), and every
            # actuator heading with its own table - a heading never gets
            # stranded at the bottom of a page with its table starting on
            # the next one, but a long floor's later actuators still
            # paginate normally.
            group = [floor_heading, Spacer(1, 2 * mm), actor_heading, table] if idx == 0 else [actor_heading, table]
            story.append(KeepTogether(group))
            story.append(Spacer(1, 5 * mm))

    return story


@router.get("/api/projects/{project_id}/export-abgangsliste.pdf")
def export_abgangsliste_pdf(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        styles = pdf_styles()
        story = company_header_block(company) + pdf_title_banner(f"Abgangsliste — {project['name']}", "Aktoren-Verdrahtung je Geschoss")
        story += build_abgangsliste_story(db, project_id, styles)

        return build_pdf_response(
            story,
            footer_left_text=f"Abgangsliste · {project['name']}",
            filename=f"{project['name'].replace(' ', '_')}_abgangsliste.pdf",
            doc_title=f"Abgangsliste {project['name']}",
            footer_center_text=company_footer_line(company),
        )


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
