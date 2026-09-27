"""The Übergabe-Checkliste tab rendered server-side (htmx)."""
import pytest

from backend.routers.checkliste import CHECKLIST_SECTIONS
from conftest import ok, seed_musterhaus


@pytest.fixture
def project(client):
    return seed_musterhaus(client)


def first_key():
    slug = CHECKLIST_SECTIONS[0][1][0][0]
    return f"uebergabe:{slug}"


def test_tab_lists_sections(client, project):
    pid = project
    body = client.get(f"/hx/projects/{pid}/handover-checklist").text
    for section_title, _items in CHECKLIST_SECTIONS:
        assert section_title in body
    assert ">Ja<" in body and ">Nein<" in body and ">Nicht nötig<" in body


def test_set_status_persists_and_toggles_off(client, project):
    pid = project
    key = first_key()

    r = client.put(f"/hx/projects/{pid}/handover-checklist/items/{key}/status/ja")
    assert r.status_code == 200 and "active" in r.text and "done" in r.text
    status = ok(client.get(f"/api/projects/{pid}/checklist-status"))[key]
    assert status["status"] == "ja" and status["updated_at"]

    # tapping the already-active option clears it
    r2 = client.put(f"/hx/projects/{pid}/handover-checklist/items/{key}/status/ja")
    assert "active" not in r2.text
    status2 = ok(client.get(f"/api/projects/{pid}/checklist-status"))[key]
    assert status2["status"] == ""


def test_set_note_persists_and_keeps_status(client, project):
    pid = project
    key = first_key()
    ok(client.put(f"/api/projects/{pid}/checklist-status/{key}", json={"status": "nein", "note": ""}))

    r = client.put(f"/hx/projects/{pid}/handover-checklist/items/{key}/note", data={"note": "Bitte prüfen"})
    assert r.status_code == 200 and "Bitte prüfen" in r.text

    status = ok(client.get(f"/api/projects/{pid}/checklist-status"))[key]
    assert status["status"] == "nein" and status["note"] == "Bitte prüfen"


def test_unknown_item_key_is_rejected(client, project):
    pid = project
    r = client.put(f"/hx/projects/{pid}/handover-checklist/items/unknown/status/ja")
    assert r.status_code == 404


def test_signatures_fragment_and_capture(client, project):
    pid = project
    body = client.get(f"/hx/projects/{pid}/handover-checklist/signatures").text
    assert "Unterschreiben" in body and "Kunde/Betreiber" in body

    png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    ok(client.put(f"/api/projects/{pid}/signatures/kunde", json={"image": png}))

    body2 = client.get(f"/hx/projects/{pid}/handover-checklist/signatures").text
    assert "Unterschrieben am" in body2
