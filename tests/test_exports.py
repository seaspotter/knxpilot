"""Every PDF/CSV/JSON export must build for a realistic project - including
names and notes with characters that are markup in ReportLab/HTML (&, <, >,
quotes), which broke several exports before."""
import pytest

from conftest import ok, seed_musterhaus

NASTY = 'Müller & Söhne – <"Test"> €'  # en dash/€ aren't Latin-1: used to 500 every download


@pytest.fixture
def project(client):
    pid = seed_musterhaus(client, name=NASTY)
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    room = tree["floors"][0]["rooms"][0]
    ok(client.put(f"/api/rooms/{room['id']}", json={"name": "Bad & WC <OG>"}))
    ok(client.post(f"/api/projects/{pid}/clarifications", json={"text": "Taster <weiss> & schwarz?", "room_id": room["id"]}))
    ok(client.post(f"/api/projects/{pid}/clarifications", json={"text": 'Allgemein "Frage"', "type": "Aufgabe"}))
    at = next(a for a in ok(client.get("/api/actor-types")) if a["model"] == "BE-GT2TW.02")
    ok(client.put(f"/api/actor-types/{at['id']}", json={**at, "description": "Taster & <Glas>"}))
    ok(client.post("/api/time-entries", json={"project_id": pid, "started_at": "2026-09-25T08:00:00Z",
                                               "ended_at": "2026-09-25T09:00:00Z", "note": "Notiz & <mehr>"}))
    cp = ok(client.get("/api/company-profile"))
    cp.update(name="Firma & Co <GmbH>", show_on_pdf=True, documentation_include_clarification_list=True,
              documentation_include_devices_per_room=True, documentation_include_circuit_list=True,
              documentation_include_group_addresses=True, documentation_include_distribution_boards=True)
    ok(client.put("/api/company-profile", json=cp))
    return pid


PDF_ENDPOINTS = [
    "export-function-checklist.pdf", "export-handover-checklist.pdf", "export-device-list.pdf",
    "export-devices-by-room.pdf", "export-specification.pdf", "export-documentation.pdf",
    "export-clarification-list.pdf", "export-distribution-boards.pdf", "export-circuit-list.pdf", "export-labels.pdf",
]


@pytest.mark.parametrize("endpoint", PDF_ENDPOINTS)
def test_project_pdf_exports(client, project, endpoint):
    r = client.get(f"/api/projects/{project}/{endpoint}")
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF")


def test_time_tracking_pdf(client, project):
    r = client.get("/api/time-entries/export.pdf", params={"tz": "Europe/Berlin"})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


@pytest.mark.parametrize("endpoint", ["export.csv", "export-circuit-list.csv", "export-json"])
def test_other_project_exports(client, project, endpoint):
    assert client.get(f"/api/projects/{project}/{endpoint}").status_code == 200


def test_content_disposition_survives_any_name():
    from backend.utils import content_disposition
    header = content_disposition('Haus – Süd "Nord".pdf')
    header.encode("latin-1")  # must be sendable as an HTTP header at all
    assert 'filename="Haus  Sud _Nord_.pdf"' in header
    assert "filename*=UTF-8''Haus%20%E2%80%93%20S%C3%BCd%20%22Nord%22.pdf" in header
