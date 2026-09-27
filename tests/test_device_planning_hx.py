"""Device planning tab ("Geräteplanung" sub-tab) rendered server-side
(htmx): the bill of materials and the per-room/per-floor device lists, via
the /hx/... endpoints in backend/routers/device_planning.py."""
from conftest import ok, seed_musterhaus


def html(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    return response.text


def _first_bedienelement(client):
    return next(t["id"] for t in ok(client.get("/api/actor-types")) if t["group_name"] == "Bedienelement")


def test_tab_renders_rooms_and_summary(client):
    pid = seed_musterhaus(client, wire=False)
    body = html(client.get(f"/hx/projects/{pid}/device-planning"))
    assert "Wohnzimmer" in body and "Erdgeschoss (EG)" in body
    assert "Geräte ohne Raum" in body
    # Musterhaus already has devices planned - the bill of materials table
    # should be showing them, not the empty-state hint.
    summary = ok(client.get(f"/api/projects/{pid}/device-summary"))
    assert summary and summary[0]["device_name"] in body


def test_tab_without_structure_shows_hint(client):
    pid = ok(client.post("/api/projects", json={"name": "Leer"}))["id"]
    body = html(client.get(f"/hx/projects/{pid}/device-planning"))
    assert "Noch keine Geschosse in diesem Projekt" in body


def test_add_edit_delete_room_device_updates_summary(client):
    pid = ok(client.post("/api/projects", json={"name": "Test"}))["id"]
    eg = ok(client.post(f"/api/projects/{pid}/floors", json={"name": "EG"}))["id"]
    room = ok(client.post(f"/api/floors/{eg}/rooms", json={"name": "Wohnzimmer"}))["id"]
    device_type_id = _first_bedienelement(client)

    body = html(client.post(f"/hx/rooms/{room}/devices",
                             data={"device_type_id": device_type_id, "quantity": "1",
                                   "note": "Neben Tür", "physical_address": "1.1.5"}))
    assert "Neben Tür" in body and "1.1.5" in body
    # the room fragment carries the summary as an out-of-band swap
    assert 'id="device-summary" hx-swap-oob="true"' in body
    summary = ok(client.get(f"/api/projects/{pid}/device-summary"))
    assert len(summary) == 1 and summary[0]["total"] == 1
    rd_id = ok(client.get(f"/api/rooms/{room}/devices"))[0]["id"]

    form = html(client.get(f"/hx/room-devices/{rd_id}/edit"))
    assert 'value="1.1.5"' in form and "Änderungen speichern" in form

    body = html(client.put(f"/hx/room-devices/{rd_id}",
                            data={"note": "Umgezogen", "physical_address": "1.1.6"}))
    assert "Umgezogen" in body and "1.1.6" in body
    device = ok(client.get(f"/api/rooms/{room}/devices"))[0]
    assert (device["note"], device["physical_address"]) == ("Umgezogen", "1.1.6")

    body = html(client.get(f"/hx/rooms/{room}/devices/cancel-edit"))
    assert "+ Hinzufügen" in body

    body = html(client.delete(f"/hx/room-devices/{rd_id}"))
    assert "Keine Geräte" in body
    assert ok(client.get(f"/api/rooms/{room}/devices")) == []
    assert ok(client.get(f"/api/projects/{pid}/device-summary")) == []


def test_add_edit_delete_floor_device(client):
    pid = ok(client.post("/api/projects", json={"name": "Test"}))["id"]
    eg = ok(client.post(f"/api/projects/{pid}/floors", json={"name": "EG"}))["id"]
    device_type_id = _first_bedienelement(client)

    body = html(client.post(f"/hx/floors/{eg}/devices",
                             data={"device_type_id": device_type_id, "quantity": "2", "note": "Fassade"}))
    assert "Fassade" in body
    devices = ok(client.get(f"/api/floors/{eg}/devices"))
    assert len(devices) == 2  # quantity=2 creates two quantity=1 rows

    fd_id = devices[0]["id"]
    form = html(client.get(f"/hx/floor-devices/{fd_id}/edit"))
    assert "Änderungen speichern" in form

    body = html(client.put(f"/hx/floor-devices/{fd_id}", data={"note": "Nord", "physical_address": "1.1.9"}))
    assert "Nord" in body and "1.1.9" in body

    body = html(client.delete(f"/hx/floor-devices/{fd_id}"))
    assert "Fassade" in body  # the other one is still there
    assert len(ok(client.get(f"/api/floors/{eg}/devices"))) == 1


def test_order_flag_toggle_updates_summary(client):
    pid = ok(client.post("/api/projects", json={"name": "Test"}))["id"]
    eg = ok(client.post(f"/api/projects/{pid}/floors", json={"name": "EG"}))["id"]
    room = ok(client.post(f"/api/floors/{eg}/rooms", json={"name": "Flur"}))["id"]
    device_type_id = _first_bedienelement(client)
    ok(client.post(f"/api/rooms/{room}/devices", json={"device_type_id": device_type_id, "quantity": 1}))

    body = html(client.put(f"/hx/projects/{pid}/device-order-flags/{device_type_id}",
                            data={"not_ordering": "true"}))
    assert "Bereits vorhanden" in body
    summary = ok(client.get(f"/api/projects/{pid}/device-summary"))
    assert summary[0]["not_ordering"] is True

    body = html(client.put(f"/hx/projects/{pid}/device-order-flags/{device_type_id}",
                            data={"not_ordering": "false"}))
    assert "Bereits vorhanden" not in body
