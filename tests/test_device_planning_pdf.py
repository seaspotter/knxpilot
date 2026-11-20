"""The Stückliste/Geräte-je-Raum PDF content (routers/device_planning.py's
build_stueckliste_story/build_devices_by_room_story) - checked at the
flowable level (Paragraph/Table text), not by parsing rendered PDF bytes:
ReportLab compresses its content streams (FlateDecode), so the exported
text isn't searchable in the raw PDF bytes at all."""
from reportlab.platypus import KeepTogether

from backend.db import get_db
from backend.pdf_design import pdf_styles, PDF_WARN_COLOR
from backend.routers.device_planning import build_devices_by_room_story, build_stueckliste_story, device_summary
from conftest import ok


def _texts(flowables):
    """Every Paragraph's raw text in a story, including inside Table cells
    (each cell is itself a Paragraph - see _cell()) and KeepTogether groups."""
    texts = []
    for f in flowables:
        if hasattr(f, "_cellvalues"):
            for row in f._cellvalues:
                texts += _texts(row)
        elif hasattr(f, "_content"):  # KeepTogether
            texts += _texts(f._content)
        elif hasattr(f, "text"):
            texts.append(f.text)
    return texts


def _three_devices(client):
    """A to-order device, an optional one, and a not-ordering one, each in
    its own room so Geräte-je-Raum also gets one row per bucket."""
    pid = ok(client.post("/api/projects", json={"name": "T"}))["id"]
    eg = ok(client.post(f"/api/projects/{pid}/floors", json={"name": "EG"}))["id"]
    rooms = {name: ok(client.post(f"/api/floors/{eg}/rooms", json={"name": name}))["id"]
             for name in ("Normal", "Optional", "Vorhanden")}
    at = {a["model"]: a["id"] for a in ok(client.get("/api/actor-types")) if a["group_name"] == "Bedienelement"}
    models = list(at)[:3]
    for name, model in zip(("Normal", "Optional", "Vorhanden"), models):
        ok(client.post(f"/api/rooms/{rooms[name]}/devices", json={"device_type_id": at[model], "quantity": 1}))
    ok(client.put(f"/api/projects/{pid}/device-optional-flags/{at[models[1]]}", json={"optional": True}))
    ok(client.put(f"/api/projects/{pid}/device-order-flags/{at[models[2]]}", json={"not_ordering": True}))
    return pid, at[models[0]], at[models[1]], at[models[2]]


def test_stueckliste_splits_optional_into_its_own_table(client):
    pid, normal_id, optional_id, not_ordering_id = _three_devices(client)
    styles = pdf_styles()
    story = build_stueckliste_story(device_summary(pid), styles)
    texts = _texts(story)

    assert "Stückliste" in texts
    assert "Optional (Kundenentscheidung)" in texts
    assert "Bereits vorhanden (nicht bestellt)" in texts

    # Regression: the heading and its table must NOT be one atomic KeepTogether
    # group - for a long table, that group never fits in a page's remaining
    # space and ReportLab defers the whole thing to a fresh page, leaving the
    # rest of the current one blank (see build_stueckliste_story's comment).
    assert not isinstance(story[0], KeepTogether)

    normal_model = next(r["model"] for r in device_summary(pid) if r["device_type_id"] == normal_id)
    optional_model = next(r["model"] for r in device_summary(pid) if r["device_type_id"] == optional_id)
    not_ordering_name = next(r["device_name"] for r in device_summary(pid) if r["device_type_id"] == not_ordering_id)

    # The optional device shows up once, under the Optional heading - not also
    # (with a suffix) in the main Stückliste table.
    assert texts.count(optional_model) == 1
    assert normal_model in texts
    # not_ordering devices are named in the "Bereits vorhanden" text, not as a table row.
    assert any(not_ordering_name in t for t in texts)


def _tables(flowables):
    for f in flowables:
        if hasattr(f, "_cellvalues"):
            yield f
        elif hasattr(f, "_content"):  # KeepTogether
            yield from _tables(f._content)


def test_devices_by_room_marks_optional_devices(client):
    pid, normal_id, optional_id, not_ordering_id = _three_devices(client)
    styles = pdf_styles()
    with get_db() as db:
        story = build_devices_by_room_story(db, pid, styles)
    texts = _texts(story)

    descriptions = [t for t in texts if "Kundenentscheidung ausstehend" in t]
    assert len(descriptions) == 1  # only the one device marked optional

    # The row is also visually flagged (warn color + bold), not just text -
    # the whole point of this change was that plain "(optional)" text was
    # too easy to miss. A Table-level TEXTCOLOR/FONTNAME command has no effect
    # on a cell that's already a Paragraph (every cell here is, via _cell()) -
    # it renders with its own style, so that's what must carry the styling.
    optional_row = next(
        row for t in _tables(story) for row in t._cellvalues
        if any(hasattr(c, "text") and "Kundenentscheidung ausstehend" in c.text for c in row)
    )
    assert all(cell.style.textColor == PDF_WARN_COLOR and cell.style.fontName == "Helvetica-Bold" for cell in optional_row)

    # A normal row must NOT be warn-styled - otherwise this wouldn't stand out at all.
    normal_row = next(
        row for t in _tables(story) for row in t._cellvalues
        if any(hasattr(c, "text") and "Kundenentscheidung" not in c.text for c in row)
    )
    assert all(cell.style.textColor != PDF_WARN_COLOR for cell in normal_row)
