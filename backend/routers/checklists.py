"""
Shared backend for the two digital on-site checklists (Funktionscheckliste,
Übergabe-Checkliste): a common checklist_status upsert mechanism (see
db.py), plus JSON endpoints that expose the already-keyed function/central-
function data (from ga_logic.py) and the static Übergabe-Checkliste catalog,
so neither frontend re-derives that filtering/grouping logic itself. Also
both tabs' PDF exports - kept in this one file rather than split across two
router files, since they need the exact same status-map-fetching logic
already written for the JSON endpoints, and the two tabs otherwise share no
router. See routers/specification.py for the early-stage spec document
these checklists' results eventually feed into (via routers/
documentation.py) and its function_checklist_table(), reused here for the
Funktionscheckliste PDF export. Also home to the Übergabe-Checkliste's
digital signature capture (project_signatures table, see db.py) - captured
via an HTML canvas signature pad in the frontend, embedded into both the
Übergabe-Checkliste and Dokumentation PDF exports via build_signature_row().
"""
import base64
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Form, HTTPException, Request, Response
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.units import mm

from ..db import get_db
from ..ga_logic import get_room_functions_by_category, get_central_functions_overview
from ..models import ChecklistStatusIn, SignatureIn
from ..pdf_design import (
    pdf_styles, pdf_title_banner, pdf_table_style, build_pdf_bytes, pdf_response,
    company_header_block, company_footer_line, checkbox_cell, signature_block,
)
from .specification import function_checklist_table
from ..templating import templates
from ..utils import local_time_text

router = APIRouter(tags=["checklists"])


# ---------- Shared checklist-status store ----------
def get_status_map(db, project_id):
    rows = db.execute(
        "SELECT item_key, status, note, updated_at FROM checklist_status WHERE project_id=?", (project_id,)
    ).fetchall()
    # updated_at = when the item was last ticked/changed (UTC, sqlite
    # CURRENT_TIMESTAMP) - shown as "getestet am" in the Funktionscheckliste.
    return {r["item_key"]: {"status": r["status"], "note": r["note"], "updated_at": r["updated_at"]} for r in rows}


@router.get("/api/projects/{project_id}/checklist-status")
def get_checklist_status(project_id: int):
    with get_db() as db:
        return get_status_map(db, project_id)


@router.put("/api/projects/{project_id}/checklist-status/{item_key}")
def set_checklist_status(project_id: int, item_key: str, body: ChecklistStatusIn):
    with get_db() as db:
        db.execute(
            "INSERT INTO checklist_status (project_id, item_key, status, note) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(project_id, item_key) DO UPDATE SET "
            "status=excluded.status, note=excluded.note, updated_at=CURRENT_TIMESTAMP",
            (project_id, item_key, body.status, body.note),
        )
    return {"ok": True}


# ---------- Funktionscheckliste ----------
@router.get("/api/rooms/{room_id}/function-checklist")
def room_function_checklist(room_id: int):
    """{category_name: [{key, text}, ...]} - same grouping the Pflichtenheft
    PDF uses, just exposed as JSON so the Funktionscheckliste tab doesn't
    have to re-derive it client-side."""
    with get_db() as db:
        return get_room_functions_by_category(db, room_id)


@router.get("/api/projects/{project_id}/central-functions-checklist")
def central_functions_checklist(project_id: int):
    """[[category_name, [{key, text}, ...]], ...] - see get_central_functions_overview()."""
    with get_db() as db:
        return get_central_functions_overview(db, project_id)


def build_function_checklist_pdf_bytes(project_id: int):
    """The on-site testing record: every planned function, grouped by
    Geschoss/Raum, with its real checked state - counterpart to
    Pflichtenheft's own "what's planned" listing, which deliberately has no
    checkbox column at all. Shared by the HTTP download endpoint below and
    routers/email.py's send-by-mail action."""
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        status_map = get_status_map(db, project_id)

        styles = pdf_styles()
        story = company_header_block(company) + pdf_title_banner(
            f"Funktionscheckliste — {project['name']}",
            "Digital erfasster Testfortschritt je Funktion",
        )

        any_room = False
        for floor in floors:
            rooms = db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall()
            if not rooms:
                continue
            floor_heading = Paragraph(floor["name"], styles["SectionHeading"])
            first_room_in_floor = True
            for room in rooms:
                functions = get_room_functions_by_category(db, room["id"])
                function_table = function_checklist_table(styles, functions, status_map=status_map)
                if not function_table:
                    continue
                any_room = True
                room_heading = Paragraph(room["name"], styles["RoomHeading"])
                group = [floor_heading, room_heading] if first_room_in_floor else [room_heading]
                first_room_in_floor = False
                group.append(function_table)
                story.append(KeepTogether(group))
                story.append(Spacer(1, 2.5 * mm))

        if not any_room:
            story.append(Paragraph("Noch keine Funktionen geplant.", styles["BodyMuted"]))

        central_overview = get_central_functions_overview(db, project_id)
        if central_overview:
            central_table = function_checklist_table(styles, dict(central_overview), status_map=status_map)
            if central_table:
                story.append(Paragraph("Zentral- und Allgemeinfunktionen", styles["SectionHeading"]))
                story.append(Spacer(1, 2 * mm))
                story.append(central_table)

        story.append(Spacer(1, 8 * mm))
        story.append(build_signature_row(db, project_id, styles, FUNCTION_CHECKLIST_SIGNATURES, optional=("fc_kunde",)))

        data = build_pdf_bytes(
            story,
            footer_left_text=f"Funktionscheckliste · {project['name']}",
            doc_title=f"Funktionscheckliste {project['name']}",
            footer_center_text=company_footer_line(company),
        )
        return data, f"{project['name'].replace(' ', '_')}_function_checklist.pdf"


@router.get("/api/projects/{project_id}/export-function-checklist.pdf")
def export_function_checklist_pdf(project_id: int):
    data, filename = build_function_checklist_pdf_bytes(project_id)
    return pdf_response(data, filename)


# ---------- htmx fragments: Funktionscheckliste (function checklist) ----------
# Tab id/JS file renamed to English (function_checklist) as part of the
# htmx migration - the JSON endpoints/PDF builder above keep their existing
# (German) names since routers/documentation.py and routers/email.py already
# depend on them; only the newly-added server-rendered surface uses the
# English naming going forward.
def checklist_dom_id(key):
    return "cl-" + "".join(c if c.isalnum() else "-" for c in key)


def _checklist_rows(by_category, status_map):
    """Flattens {category: [{key, text}, ...]} into render-ready rows (with
    checked/when precomputed) so the templates stay plain loops."""
    rows = []
    for cat_name, items in by_category.items():
        for item in items:
            entry = status_map.get(item["key"], {})
            checked = entry.get("status") == "ok"
            rows.append({
                "key": item["key"], "text": item["text"], "cat": cat_name,
                "checked": checked,
                "when": local_time_text(entry.get("updated_at")) if checked else "",
                "dom_id": checklist_dom_id(item["key"]),
            })
    return rows


def _function_checklist_context(db, project_id):
    status_map = get_status_map(db, project_id)
    floors_out = []
    for floor in db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall():
        rooms_out = []
        for room in db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall():
            by_category = get_room_functions_by_category(db, room["id"])
            if not by_category:
                continue
            rooms_out.append({"name": room["name"], "rows": _checklist_rows(by_category, status_map)})
        if rooms_out:
            floors_out.append({"name": floor["name"], "rooms": rooms_out})
    central = dict(get_central_functions_overview(db, project_id))
    central_rows = _checklist_rows(central, status_map) if central else []
    signatures = {
        r["role"]: {"signed_at": r["signed_at"]}
        for r in db.execute(
            "SELECT role, signed_at FROM project_signatures WHERE project_id=?", (project_id,)
        ).fetchall()
    }
    return {
        "project_id": project_id,
        "floors": floors_out,
        "central_rows": central_rows,
        "signatures": signatures,
        "local_time_text": local_time_text,
    }


@router.get("/hx/projects/{project_id}/function-checklist")
def hx_function_checklist_tab(request: Request, project_id: int):
    with get_db() as db:
        ctx = _function_checklist_context(db, project_id)
    return templates.TemplateResponse(request, "function_checklist/tab.html", ctx)


@router.put("/hx/projects/{project_id}/function-checklist/items/{item_key}")
def hx_function_checklist_toggle(request: Request, project_id: int, item_key: str, cat: str = ""):
    """Toggles a single item's ok/unchecked state and returns just that
    row's fragment - deliberately not a full-tab re-render (this list can be
    every room x every function; re-rendering all of it after each tap would
    reset scroll position while walking through a building)."""
    with get_db() as db:
        current = db.execute(
            "SELECT status FROM checklist_status WHERE project_id=? AND item_key=?", (project_id, item_key)
        ).fetchone()
        new_status = "" if current and current["status"] == "ok" else "ok"
        db.execute(
            "INSERT INTO checklist_status (project_id, item_key, status, note) VALUES (?, ?, ?, '') "
            "ON CONFLICT(project_id, item_key) DO UPDATE SET "
            "status=excluded.status, updated_at=CURRENT_TIMESTAMP",
            (project_id, item_key, new_status),
        )
        entry = get_status_map(db, project_id).get(item_key, {})
    checked = new_status == "ok"
    row = {
        "key": item_key, "text": request.query_params.get("text", ""), "cat": cat,
        "checked": checked, "when": local_time_text(entry.get("updated_at")) if checked else "",
        "dom_id": checklist_dom_id(item_key),
    }
    return templates.TemplateResponse(request, "function_checklist/_row.html", {"project_id": project_id, "row": row})


@router.get("/hx/projects/{project_id}/function-checklist/signatures")
def hx_function_checklist_signatures(request: Request, project_id: int):
    with get_db() as db:
        signatures = {
            r["role"]: {"signed_at": r["signed_at"]}
            for r in db.execute(
                "SELECT role, signed_at FROM project_signatures WHERE project_id=?", (project_id,)
            ).fetchall()
        }
    return templates.TemplateResponse(request, "function_checklist/_signatures.html", {
        "project_id": project_id, "signatures": signatures, "local_time_text": local_time_text,
    })


# ---------- Übergabe-Checkliste ----------
# Generic, mostly project-independent handover checklist - its own sub-tab,
# checked digitally on-site (PDF is an export/snapshot only, not the
# primary interface). Scoped deliberately to the system integrator's own
# work (programming/commissioning/troubleshooting, customer walkthrough,
# handover) - NOT physical installation work (mounting devices, wiring,
# labeling boxes/distribution boards, E-Check etc.), which is the
# electrician's responsibility and out of scope for this tool's user.
# Each item has a hand-assigned stable slug (not derived from its text) so
# its checklist_status key survives a future wording tweak without
# silently resetting anyone's saved answer - only reordering/removing an
# item invalidates its key.
CHECKLIST_SECTIONS = [
    ("Funktionsprüfung", [
        ("funktionen_geprueft", "Licht, Dimmer, Jalousien, Zentral Aus, Szenen usw. auf korrekte Funktion geprüft"),
        ("fensterkontakte_geprueft", "Fensterkontakte geprüft"),
        ("gegensprechanlage_geprueft", "Sprechanlage geprüft"),
        ("schnittstellen_geprueft", "Schnittstellen zu Fremdsystemen geprüft (PV-Anlage, Wärmepumpe, Alarm, Lüftung usw.)"),
    ]),
    ("Kundengespräch", [
        ("einfuehrung_installation", "Einführung des Kunden in die technische Installation"),
        ("einweisung_geraetestandort", "Einweisung über den Standort spezieller Geräte (z.B. Windfühler, Zentrale)"),
        ("einweisung_sicherheit", "Einweisung in Sicherheitsanwendungen und Alarmzentrale"),
        ("erlaeuterung_funktionen", "Erläuterung der Schalt-, Dimm- und Jalousiefunktionen"),
        ("erklaerung_visualisierung", "Erklärung von Inhalten und Navigation von Touchpanels/Visualisierungen"),
        ("einweisung_schaltuhren", "Einweisung in Schaltuhren und weitere kundenrelevante Funktionen (z.B. Szenen abrufen/speichern)"),
        ("einweisung_raumbediengeraete", "Einweisung in die Bedienung der Raumtemperaturregler und weiterer Raumbediengeräte"),
        ("verhalten_ausfall_besprochen", "Verhalten bei Bus-/Netzspannungsausfall und -wiederkehr besprochen"),
        ("offene_punkte_aufgenommen", "Offene Punkte aufgenommen"),
    ]),
    ("Anlagenübergabe", [
        ("bedienungsanleitungen_uebergeben", "Bedienungsanleitungen übergeben"),
        ("anlagendokumentation_uebergeben", "Anlagendokumentation (Pläne, Checklisten, Finale Dokumentation) übergeben"),
        ("software_backups_uebergeben", "Software und Backups übergeben (ETS-Software, Visualisierung)"),
        ("passwoerter_uebergeben", "Passwörter übergeben"),
        ("kundendienst_hinterlassen", "Kundendienst-Kontaktdaten hinterlassen / Wartungsvertrag angeboten/abgeschlossen"),
        ("abnahmeprotokoll_unterzeichnet", "Übergabe-Protokoll unterzeichnet"),
    ]),
]


@router.get("/api/handover-checklist-sections")
def handover_checklist_sections():
    """Project-independent - the frontend always gets its item keys from
    here rather than inventing/hashing them itself."""
    return [
        {
            "section": section_title,
            "items": [{"key": f"handover:{slug}", "text": text} for slug, text in items],
        }
        for section_title, items in CHECKLIST_SECTIONS
    ]


def checklist_section_table(styles, items, status_map):
    data = [["Aufgabe", "Ja", "Nein", "Nicht nötig", "Bemerkungen"]]
    for slug, text in items:
        entry = status_map.get(f"handover:{slug}", {})
        status = entry.get("status", "")
        note = entry.get("note", "")
        data.append([
            Paragraph(text, styles["Body"]),
            checkbox_cell(checked=status == "ja"),
            checkbox_cell(checked=status == "nein"),
            checkbox_cell(checked=status == "nicht_noetig"),
            Paragraph(note, styles["Body"]) if note else "",
        ])
    table = Table(data, colWidths=[85 * mm, 12 * mm, 12 * mm, 20 * mm, 51 * mm], repeatRows=1)
    table.setStyle(pdf_table_style([
        ("ALIGN", (1, 0), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


# ---------- Digital signatures ----------
# Captured on-site via an HTML canvas signature pad (frontend/js/
# handover_checklist.js) instead of printing the PDF and signing on
# paper. Editable/re-signable at any time (UNIQUE(project_id, role) makes
# re-signing a plain upsert, same idiom as checklist_status/
# device_order_flags) and independently deletable per role.
# Übergabe-Checkliste: systemintegrator/kunde. The Funktionscheckliste has its
# own pair (fc_*) - confirming the functions were tested is a separate act
# from signing the handover; the customer's is optional there.
SIGNATURE_ROLES = {"systemintegrator", "kunde", "fc_systemintegrator", "fc_kunde"}
HANDOVER_SIGNATURES = (("systemintegrator", "Systemintegrator"), ("kunde", "Kunde/Betreiber"))
FUNCTION_CHECKLIST_SIGNATURES = (("fc_systemintegrator", "Systemintegrator"), ("fc_kunde", "Kunde/Betreiber"))


@router.get("/api/projects/{project_id}/signatures")
def get_signatures(project_id: int):
    with get_db() as db:
        rows = db.execute(
            "SELECT role, signed_at FROM project_signatures WHERE project_id=?", (project_id,)
        ).fetchall()
        return {r["role"]: {"signed_at": r["signed_at"]} for r in rows}


@router.get("/api/projects/{project_id}/signatures/{role}/image")
def get_signature_image(project_id: int, role: str):
    with get_db() as db:
        row = db.execute(
            "SELECT image FROM project_signatures WHERE project_id=? AND role=?", (project_id, role)
        ).fetchone()
    if not row:
        raise HTTPException(404, "No signature")
    return Response(content=row["image"], media_type="image/png")


@router.put("/api/projects/{project_id}/signatures/{role}")
def set_signature(project_id: int, role: str, body: SignatureIn):
    if role not in SIGNATURE_ROLES:
        raise HTTPException(400, "Unknown signature role")
    b64data = body.image.split(";base64,", 1)[-1]
    try:
        image_bytes = base64.b64decode(b64data)
    except Exception:
        raise HTTPException(400, "Invalid image data")
    signed_at = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO project_signatures (project_id, role, image, signed_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(project_id, role) DO UPDATE SET image=excluded.image, signed_at=excluded.signed_at",
            (project_id, role, image_bytes, signed_at),
        )
    return {"signed_at": signed_at}


@router.delete("/api/projects/{project_id}/signatures/{role}")
def delete_signature(project_id: int, role: str):
    with get_db() as db:
        db.execute("DELETE FROM project_signatures WHERE project_id=? AND role=?", (project_id, role))
    return {"ok": True}


def build_signature_row(db, project_id, styles, roles=HANDOVER_SIGNATURES, optional=()):
    """The Systemintegrator/Kunde signature row at the end of the Übergabe-
    Checkliste / Funktionscheckliste (and, via routers/documentation.py, the
    Dokumentation) PDF - renders the real captured signature + "signiert am"
    timestamp for whichever roles have one, and a blank paper-style line for
    the rest. Roles in `optional` are left out entirely when unsigned."""
    rows = {
        r["role"]: r
        for r in db.execute(
            "SELECT role, image, signed_at FROM project_signatures WHERE project_id=?", (project_id,)
        ).fetchall()
    }

    def block(role, label):
        row = rows.get(role)
        if not row:
            return signature_block(label, styles)
        return signature_block(label, styles, image_bytes=row["image"], signed_at_text=local_time_text(row["signed_at"]))

    cells = [block(role, label) for role, label in roles if role in rows or role not in optional]
    sig_row = Table([cells], colWidths=[90 * mm] * len(cells), hAlign="LEFT")
    sig_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return sig_row


def build_handover_checklist_pdf_bytes(project_id: int):
    """Shared by the HTTP download endpoint below and routers/email.py's
    send-by-mail action."""
    styles = pdf_styles()
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        company = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        status_map = get_status_map(db, project_id)
        sig_row = build_signature_row(db, project_id, styles)

    story = company_header_block(company) + pdf_title_banner(
        f"Übergabe-Checkliste — {project['name']}",
        "Checkliste zur Übergabe einer Elektroinstallation mit KNX",
    )

    for i, (section_title, items) in enumerate(CHECKLIST_SECTIONS):
        if i > 0:
            story.append(Spacer(1, 4 * mm))
        story.append(KeepTogether([
            Paragraph(section_title, styles["SectionHeading"]),
            checklist_section_table(styles, items, status_map),
        ]))

    story.append(Spacer(1, 8 * mm))
    story.append(sig_row)

    data = build_pdf_bytes(
        story,
        footer_left_text=f"Übergabe-Checkliste · {project['name']}",
        doc_title=f"Übergabe-Checkliste {project['name']}",
        footer_center_text=company_footer_line(company),
    )
    return data, f"{project['name'].replace(' ', '_')}_handover_checklist.pdf"


@router.get("/api/projects/{project_id}/export-handover-checklist.pdf")
def export_handover_checklist_pdf(project_id: int):
    data, filename = build_handover_checklist_pdf_bytes(project_id)
    return pdf_response(data, filename)


# ---------- htmx fragments: Übergabe-Checkliste (handover checklist) ----------
# Unlike the Funktionscheckliste, a status click here re-renders just that
# one row too (not the whole section) - each row's own fragment carries its
# 3-way Ja/Nein/Nicht-nötig switch and its Bemerkungen field.
HANDOVER_ITEMS_BY_KEY = {
    f"handover:{slug}": text for _section, items in CHECKLIST_SECTIONS for slug, text in items
}


def _handover_row(item_key, status_map):
    entry = status_map.get(item_key, {})
    status = entry.get("status", "")
    return {
        "key": item_key, "text": HANDOVER_ITEMS_BY_KEY[item_key],
        "status": status, "note": entry.get("note", ""),
        "when": local_time_text(entry.get("updated_at")) if status else "",
        "dom_id": checklist_dom_id(item_key),
    }


def _handover_checklist_context(db, project_id):
    status_map = get_status_map(db, project_id)
    sections = [
        {"section": title, "rows": [_handover_row(f"handover:{slug}", status_map) for slug, _text in items]}
        for title, items in CHECKLIST_SECTIONS
    ]
    signatures = {
        r["role"]: {"signed_at": r["signed_at"]}
        for r in db.execute(
            "SELECT role, signed_at FROM project_signatures WHERE project_id=?", (project_id,)
        ).fetchall()
    }
    return {"project_id": project_id, "sections": sections, "signatures": signatures, "local_time_text": local_time_text}


@router.get("/hx/projects/{project_id}/handover-checklist")
def hx_handover_checklist_tab(request: Request, project_id: int):
    with get_db() as db:
        ctx = _handover_checklist_context(db, project_id)
    return templates.TemplateResponse(request, "handover_checklist/tab.html", ctx)


@router.put("/hx/projects/{project_id}/handover-checklist/items/{item_key}/status/{status}")
def hx_handover_checklist_set_status(request: Request, project_id: int, item_key: str, status: str):
    """Tapping the already-active option clears it (status -> ''), matching
    the previous classic-JS behavior."""
    if item_key not in HANDOVER_ITEMS_BY_KEY:
        raise HTTPException(404, "Unknown checklist item")
    with get_db() as db:
        current = db.execute(
            "SELECT status, note FROM checklist_status WHERE project_id=? AND item_key=?", (project_id, item_key)
        ).fetchone()
        note = current["note"] if current else ""
        new_status = "" if current and current["status"] == status else status
        db.execute(
            "INSERT INTO checklist_status (project_id, item_key, status, note) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(project_id, item_key) DO UPDATE SET "
            "status=excluded.status, updated_at=CURRENT_TIMESTAMP",
            (project_id, item_key, new_status, note),
        )
        row = _handover_row(item_key, get_status_map(db, project_id))
    return templates.TemplateResponse(request, "handover_checklist/_row.html", {"project_id": project_id, "row": row})


@router.put("/hx/projects/{project_id}/handover-checklist/items/{item_key}/note")
def hx_handover_checklist_set_note(request: Request, project_id: int, item_key: str, note: str = Form("")):
    if item_key not in HANDOVER_ITEMS_BY_KEY:
        raise HTTPException(404, "Unknown checklist item")
    with get_db() as db:
        current = db.execute(
            "SELECT status FROM checklist_status WHERE project_id=? AND item_key=?", (project_id, item_key)
        ).fetchone()
        status = current["status"] if current else ""
        db.execute(
            "INSERT INTO checklist_status (project_id, item_key, status, note) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(project_id, item_key) DO UPDATE SET "
            "note=excluded.note, updated_at=CURRENT_TIMESTAMP",
            (project_id, item_key, status, note),
        )
        row = _handover_row(item_key, get_status_map(db, project_id))
    return templates.TemplateResponse(request, "handover_checklist/_row.html", {"project_id": project_id, "row": row})


@router.get("/hx/projects/{project_id}/handover-checklist/signatures")
def hx_handover_checklist_signatures(request: Request, project_id: int):
    with get_db() as db:
        signatures = {
            r["role"]: {"signed_at": r["signed_at"]}
            for r in db.execute(
                "SELECT role, signed_at FROM project_signatures WHERE project_id=?", (project_id,)
            ).fetchall()
        }
    return templates.TemplateResponse(request, "handover_checklist/_signatures.html", {
        "project_id": project_id, "signatures": signatures, "local_time_text": local_time_text,
    })
