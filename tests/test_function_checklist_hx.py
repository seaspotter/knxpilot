"""The Funktionscheckliste tab rendered server-side (htmx)."""
import pytest

from conftest import ok, seed_musterhaus


@pytest.fixture
def project(client):
    return seed_musterhaus(client)


def test_tab_lists_rooms_and_functions(client, project):
    pid = project
    body = client.get(f"/hx/projects/{pid}/function-checklist").text
    assert "fc-row" in body
    assert "getestet" in body


def test_toggle_item_updates_status_and_returns_row(client, project):
    pid = project
    room_id = ok(client.get(f"/api/projects/{pid}/tree"))["floors"][0]["rooms"][0]["id"]
    by_category = ok(client.get(f"/api/rooms/{room_id}/function-checklist"))
    key = next(iter(by_category.values()))[0]["key"]

    body = client.get(f"/hx/projects/{pid}/function-checklist").text
    assert f'value="{key}"' not in body  # sanity: key isn't leaked as a raw attribute value

    r = client.put(f"/hx/projects/{pid}/function-checklist/items/{key}?cat=Test&text=Testfunktion")
    assert r.status_code == 200
    assert "checked" in r.text and "done" in r.text

    status = ok(client.get(f"/api/projects/{pid}/checklist-status"))[key]
    assert status["status"] == "ok" and status["updated_at"]

    # toggling again clears it
    r2 = client.put(f"/hx/projects/{pid}/function-checklist/items/{key}?cat=Test&text=Testfunktion")
    assert "checked" not in r2.text
    status2 = ok(client.get(f"/api/projects/{pid}/checklist-status"))[key]
    assert status2["status"] == ""


def test_signatures_fragment_and_capture(client, project):
    pid = project
    body = client.get(f"/hx/projects/{pid}/function-checklist/signatures").text
    assert "Unterschreiben" in body and "Systemintegrator" in body

    png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    ok(client.put(f"/api/projects/{pid}/signatures/fc_systemintegrator", json={"image": png}))

    body2 = client.get(f"/hx/projects/{pid}/function-checklist/signatures").text
    assert "Unterschrieben am" in body2 and "Neu unterschreiben" in body2
