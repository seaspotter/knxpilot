"""Labels tab rendered server-side (htmx): the plain form via
backend/routers/labels.py's /hx/... endpoint. The label-sheet PDF export
itself is covered by tests/test_exports.py (export-labels.pdf)."""
from conftest import ok, seed_musterhaus


def html(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    return response.text


def test_tab_renders_format_options(client):
    pid = ok(client.post("/api/projects", json={"name": "Test"}))["id"]
    body = html(client.get(f"/hx/projects/{pid}/labels"))
    assert "Avery Zweckform L6037" in body
    assert 'data-size="189"' in body
    assert 'id="label-format"' in body


def test_export_includes_room_devices_without_any_actor(client):
    """A project with only a room device carrying a physical address (no
    actor instances at all) must still produce labels - regression for the
    export only ever reading actor_instances."""
    pid = seed_musterhaus(client, wire=False)
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    room = tree["floors"][0]["rooms"][0]
    device_type = ok(client.get("/api/actor-types"))[0]
    rd = ok(client.post(f"/api/rooms/{room['id']}/devices",
                         json={"device_type_id": device_type["id"], "quantity": 1, "note": "", "physical_address": ""}))
    ok(client.put(f"/api/room-devices/{rd['id']}", json={"note": "Wetterstation", "physical_address": "1.1.5"}))

    r = client.get(f"/api/projects/{pid}/export-labels.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_export_fails_without_any_addressed_device(client):
    pid = ok(client.post("/api/projects", json={"name": "Leer"}))["id"]
    r = client.get(f"/api/projects/{pid}/export-labels.pdf")
    assert r.status_code == 400
