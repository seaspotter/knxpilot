"""Functions tab ("Funktionen" sub-tab) rendered server-side (htmx): room
function assignments and special addresses ("Sonderadressen"), via the
/hx/... endpoints in backend/routers/functions.py."""
from conftest import ok, seed_musterhaus


def html(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    return response.text


def test_tab_renders_rooms_and_points(client):
    pid = seed_musterhaus(client, wire=False)
    body = html(client.get(f"/hx/projects/{pid}/functions"))
    assert "Wohnzimmer" in body and "Erdgeschoss (EG)" in body
    assert "Decke Spots" in body


def test_tab_without_structure_shows_hint(client):
    pid = ok(client.post("/api/projects", json={"name": "Leer"}))["id"]
    body = html(client.get(f"/hx/projects/{pid}/functions"))
    assert "Noch keine Geschosse" in body


def test_add_edit_delete_room_point(client):
    pid = ok(client.post("/api/projects", json={"name": "Test"}))["id"]
    eg = ok(client.post(f"/api/projects/{pid}/floors", json={"name": "EG"}))["id"]
    room = ok(client.post(f"/api/floors/{eg}/rooms", json={"name": "Wohnzimmer"}))["id"]
    pt_id = ok(client.get("/api/point-types"))[0]["id"]

    body = html(client.post(f"/hx/rooms/{room}/points",
                             data={"point_type_id": pt_id, "label": "Decke", "quantity": "1"}))
    assert "Decke" in body
    room_tree = ok(client.get(f"/api/projects/{pid}/tree"))["floors"][0]["rooms"][0]
    assert len(room_tree["points"]) == 1
    rp_id = room_tree["points"][0]["id"]

    form = html(client.get(f"/hx/room-points/{rp_id}/edit"))
    assert 'value="Decke"' in form and "Änderungen speichern" in form

    body = html(client.put(f"/hx/room-points/{rp_id}",
                            data={"point_type_id": pt_id, "label": "Nord", "has_bwm": "true"}))
    assert "Nord" in body and "+BWM" in body
    point = ok(client.get(f"/api/projects/{pid}/tree"))["floors"][0]["rooms"][0]["points"][0]
    assert (point["label"], point["has_bwm"]) == ("Nord", True)

    body = html(client.get(f"/hx/rooms/{room}/cancel-edit"))
    assert "+ Hinzufügen" in body

    body = html(client.delete(f"/hx/room-points/{rp_id}"))
    assert "Noch keine Funktionen" in body
    assert ok(client.get(f"/api/projects/{pid}/tree"))["floors"][0]["rooms"][0]["points"] == []


def test_special_addresses_add_and_delete(client):
    pid = ok(client.post("/api/projects", json={"name": "Test"}))["id"]
    cat_id = ok(client.get("/api/categories"))[0]["id"]

    body = html(client.get(f"/hx/projects/{pid}/special-addresses"))
    assert "Noch keine" in body

    body = html(client.post(f"/hx/projects/{pid}/special-addresses",
                             data={"category_id": cat_id, "location": "central", "name": "Langschläfer Kind1",
                                   "suffix": ["Auf", "Ab"], "dpt": ["DPST-1-8", "DPST-1-8"]}))
    assert "Langschläfer Kind1" in body and "Zentral" in body
    special = ok(client.get(f"/api/projects/{pid}/specials"))[0]
    assert special["name"] == "Langschläfer Kind1" and len(special["suffixes"]) == 2

    body = html(client.delete(f"/hx/special-addresses/{special['id']}"))
    assert "Noch keine" in body
    assert ok(client.get(f"/api/projects/{pid}/specials")) == []


def test_special_address_missing_name_or_suffix_is_ignored(client):
    pid = ok(client.post("/api/projects", json={"name": "Test"}))["id"]
    cat_id = ok(client.get("/api/categories"))[0]["id"]
    client.post(f"/hx/projects/{pid}/special-addresses",
                data={"category_id": cat_id, "location": "central", "name": "", "suffix": [], "dpt": []})
    assert ok(client.get(f"/api/projects/{pid}/specials")) == []
