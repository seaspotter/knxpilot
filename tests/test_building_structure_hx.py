"""
routers/building_structure.py: floor/room CRUD and the project tree, split
out of routers/projects.py when the Gebäudestruktur sub-tab was reorganized
(drag & drop / move endpoints stay covered by test_building_structure_move.py).
"""
from conftest import ok


def new_project(client, name="Testhaus"):
    return ok(client.post("/api/projects", json={"name": name}))["id"]


def test_floor_and_room_crud(client):
    pid = new_project(client)
    floor_id = ok(client.post(f"/api/projects/{pid}/floors", json={"name": "EG", "is_outdoor": False}))["id"]

    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    assert [f["name"] for f in tree["floors"]] == ["EG"]

    ok(client.put(f"/api/floors/{floor_id}", json={"name": "Erdgeschoss", "is_outdoor": False}))
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    assert tree["floors"][0]["name"] == "Erdgeschoss"

    room_id = ok(client.post(f"/api/floors/{floor_id}/rooms", json={"name": "Küche"}))["id"]
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    assert [r["name"] for r in tree["floors"][0]["rooms"]] == ["Küche"]

    ok(client.put(f"/api/rooms/{room_id}", json={"name": "Wohnküche"}))
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    assert tree["floors"][0]["rooms"][0]["name"] == "Wohnküche"

    impact = ok(client.get(f"/api/rooms/{room_id}/delete-impact"))
    assert impact == {
        "name": "Wohnküche", "points": 0, "assignments": 0, "devices": 0, "clarifications": 0,
        "specials": 0, "actors_detached": 0, "distribution_boards_detached": 0,
    }

    ok(client.delete(f"/api/rooms/{room_id}"))
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    assert tree["floors"][0]["rooms"] == []

    ok(client.delete(f"/api/floors/{floor_id}"))
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    assert tree["floors"] == []


def test_floor_delete_impact_not_found(client):
    assert client.get("/api/floors/999999/delete-impact").status_code == 404


def test_room_delete_impact_not_found(client):
    assert client.get("/api/rooms/999999/delete-impact").status_code == 404


def test_tree_project_not_found(client):
    assert client.get("/api/projects/999999/tree").status_code == 404
