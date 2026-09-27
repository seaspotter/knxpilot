"""The overview ("Übersicht") tab rendered server-side (htmx): one stat
card per sub-tab, aggregated from the same data each sub-tab itself shows,
plus the project files ("Dateien") section."""
from conftest import ok, seed_musterhaus


def test_overview_cards_match_project_state(client):
    pid = seed_musterhaus(client)
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    floor_count = len(tree["floors"])
    room_count = sum(len(f["rooms"]) for f in tree["floors"])
    circuits = ok(client.get(f"/api/projects/{pid}/circuits"))
    assigned = sum(1 for c in circuits if c["assignment"])

    body = client.get(f"/hx/projects/{pid}/overview").text
    assert f"{floor_count} Geschosse · {room_count} Räume" in body
    assert f"{assigned} / {len(circuits)} Abgänge zugeordnet" in body
    assert "goToSubtab('struktur')" in body and "goToSubtab('manuals')" in body
    assert "goToSubtab('specification')" in body and "goToSubtab('documentation')" in body
    if assigned < len(circuits):
        assert 'color:var(--warn)' in body


def test_overview_reflects_open_clarifications_and_checklist_progress(client):
    pid = seed_musterhaus(client)
    room = ok(client.get(f"/api/projects/{pid}/tree"))["floors"][0]["rooms"][0]
    ok(client.post(f"/api/projects/{pid}/klaerungen", json={"text": "offene Frage?", "room_id": room["id"]}))
    key = next(iter(ok(client.get(f"/api/rooms/{room['id']}/function-checklist")).values()))[0]["key"]
    ok(client.put(f"/api/projects/{pid}/checklist-status/{key}", json={"status": "ok", "note": ""}))

    body = client.get(f"/hx/projects/{pid}/overview").text
    assert "1 offene Einträge" in body
    assert "1 / " in body and "Funktionen getestet" in body


def test_files_upload_list_download_delete(client):
    pid = seed_musterhaus(client)
    body = client.get(f"/hx/projects/{pid}/files").text
    assert "Noch keine Dateien" in body

    body = client.post(f"/hx/projects/{pid}/files", files={"file": ("Plan Süd <EG>.pdf", b"%PDF-1.4 plan", "application/pdf")}).text
    assert "Plan S" in body and "Löschen" in body
    files = ok(client.get(f"/api/projects/{pid}/files"))
    assert len(files) == 1 and files[0]["filename"] == "Plan Süd <EG>.pdf"
    file_id = files[0]["id"]

    r = client.get(f"/api/project-files/{file_id}/download")
    assert r.status_code == 200 and r.content == b"%PDF-1.4 plan"

    body = client.delete(f"/hx/project-files/{file_id}").text
    assert "Noch keine Dateien" in body
    assert ok(client.get(f"/api/projects/{pid}/files")) == []
    assert client.delete(f"/hx/project-files/{file_id}").status_code == 404
