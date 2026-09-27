"""Distribution board planning tab rendered server-side (htmx): creating a
board, editing it, placing RCD/LS/device items, moving and removing them -
via the /hx/... endpoints in backend/routers/distribution_boards.py."""
from conftest import ok, seed_musterhaus


def html(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    return response.text


def test_tab_renders_create_form_and_empty_list(client):
    pid = seed_musterhaus(client, wire=False)
    body = html(client.get(f"/hx/projects/{pid}/distribution-boards"))
    assert "Verteiler anlegen" in body and "Noch keine Verteiler angelegt" in body
    assert "Erdgeschoss (EG) (ganzes Geschoss)" in body


def test_create_edit_delete_roundtrip(client):
    pid = seed_musterhaus(client, wire=False)
    eg = ok(client.get(f"/api/projects/{pid}/tree"))["floors"][0]

    body = html(client.post(f"/hx/projects/{pid}/distribution-boards",
                             data={"location": f"floor:{eg['id']}", "name": "UV EG", "row_count": "2"}))
    assert "UV EG" in body and "Erdgeschoss (EG)" in body
    board = ok(client.get(f"/api/projects/{pid}/distribution-boards"))[0]
    assert (board["name"], board["row_count"], board["floor_id"]) == ("UV EG", 2, eg["id"])

    form = html(client.get(f"/hx/distribution-boards/{board['id']}/edit"))
    assert "Verteiler bearbeiten" in form and 'value="UV EG"' in form

    r = client.put(f"/hx/distribution-boards/{board['id']}", data={"name": "UV Keller", "row_count": "3"})
    assert r.headers.get("HX-Trigger") == '{"hx-modal-close": true}'
    assert "UV Keller" in html(r)
    board = ok(client.get(f"/api/projects/{pid}/distribution-boards"))[0]
    assert (board["name"], board["row_count"]) == ("UV Keller", 3)

    body = html(client.delete(f"/hx/distribution-boards/{board['id']}"))
    assert "Noch keine Verteiler angelegt" in body
    assert ok(client.get(f"/api/projects/{pid}/distribution-boards")) == []


def test_add_move_delete_items(client):
    pid = seed_musterhaus(client, wire=False)
    eg = ok(client.get(f"/api/projects/{pid}/tree"))["floors"][0]
    board_id = ok(client.post(f"/api/projects/{pid}/distribution-boards", json={"floor_id": eg["id"], "name": "UV EG"}))["id"]

    body = html(client.post(f"/hx/distribution-boards/{board_id}/items",
                             data={"row_idx": "0", "item_type": "rcd"}))
    assert "RCD" in body and "8 TE frei" in body

    html(client.post(f"/hx/distribution-boards/{board_id}/items", data={"row_idx": "0", "item_type": "ls"}))
    board = ok(client.get(f"/api/projects/{pid}/distribution-boards"))[0]
    items = board["rows"][0]
    assert [(i["item_type"], i["width_te"]) for i in items] == [("rcd", 4), ("ls", 1)]

    ls_id = items[1]["id"]
    html(client.post(f"/hx/distribution-board-items/{ls_id}/move", data={"direction": "left"}))
    board = ok(client.get(f"/api/projects/{pid}/distribution-boards"))[0]
    assert [i["item_type"] for i in board["rows"][0]] == ["ls", "rcd"]

    body = html(client.delete(f"/hx/distribution-board-items/{ls_id}"))
    assert "RCD" in body
    board = ok(client.get(f"/api/projects/{pid}/distribution-boards"))[0]
    assert [i["item_type"] for i in board["rows"][0]] == ["rcd"]


def test_add_device_form_and_placement(client):
    pid = ok(client.post("/api/projects", json={"name": "Leer"}))["id"]
    eg = ok(client.post(f"/api/projects/{pid}/floors", json={"name": "EG"}))
    board_id = ok(client.post(f"/api/projects/{pid}/distribution-boards", json={"floor_id": eg["id"], "name": "UV EG"}))["id"]
    at = {a["model"]: a["id"] for a in ok(client.get("/api/actor-types"))}
    actor = ok(client.post(f"/api/projects/{pid}/actor-instances",
                            json={"actor_type_id": at["AKS-2016.03"], "floor_id": eg["id"], "location_label": "Verteilung"}))

    form = html(client.get(f"/hx/distribution-boards/{board_id}/rows/0/add-device"))
    assert "Gerät hinzufügen" in form and f'value="{actor["id"]}"' in form and "12 TE" in form

    r = client.post(f"/hx/distribution-boards/{board_id}/items",
                     data={"row_idx": "0", "item_type": "device", "actor_instance_id": str(actor["id"])})
    assert r.headers.get("HX-Trigger") == '{"hx-modal-close": true}'
    body = html(r)
    assert "MDT AKS-2016.03" in body

    # placed devices no longer show up as candidates
    form = html(client.get(f"/hx/distribution-boards/{board_id}/rows/0/add-device"))
    assert "Keine verfügbaren Geräte" in form

    # placing the same device twice is rejected
    assert client.post(f"/hx/distribution-boards/{board_id}/items",
                        data={"row_idx": "0", "item_type": "device", "actor_instance_id": str(actor["id"])}).status_code == 400
