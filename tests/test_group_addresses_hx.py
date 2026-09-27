"""Group addresses tab ("Gruppenadressen" sub-tab) rendered server-side
(htmx): the GA tree preview and what changed since the last ETS export, via
the /hx/... endpoints in backend/routers/group_addresses.py. The CSV export
itself and its golden file are covered by tests/test_ga_export.py."""
from conftest import ok, seed_musterhaus


def html(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    return response.text


def test_tab_renders_preview_tree_and_no_export_hint(client):
    pid = seed_musterhaus(client, wire=False)
    body = html(client.get(f"/hx/projects/{pid}/group-addresses"))
    assert "noch kein ETS-Export erfasst" in body
    assert "Wohnzimmer" in body  # GA names include the room name
    assert "tree-main" in body


def test_changes_after_snapshot_then_after_a_structural_change(client):
    pid = seed_musterhaus(client, wire=False)

    r = client.post(f"/hx/projects/{pid}/group-addresses/snapshot")
    assert r.status_code == 200
    assert "show-toast" in r.headers.get("HX-Trigger", "")
    body = html(r)
    assert "auf dem aktuellen Stand" in body

    # Renaming a room changes its function GAs' names -> shows up as "changed".
    room_id = ok(client.get(f"/api/projects/{pid}/tree"))["floors"][0]["rooms"][0]["id"]
    client.put(f"/api/rooms/{room_id}", json={"name": "Wohnzimmer neu"})

    body = html(client.get(f"/hx/projects/{pid}/group-addresses/changes"))
    assert "Geändert" in body


def test_csv_download_refreshes_snapshot(client):
    pid = seed_musterhaus(client, wire=False)
    r = client.get(f"/api/projects/{pid}/export.csv")
    assert r.status_code == 200
    body = html(client.get(f"/hx/projects/{pid}/group-addresses/changes"))
    assert "auf dem aktuellen Stand" in body
