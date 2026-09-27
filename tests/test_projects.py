from conftest import ok, seed_musterhaus


def test_floor_delete_impact_and_cleanup(client):
    pid = seed_musterhaus(client)
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    floor = tree["floors"][0]
    cat = ok(client.get("/api/categories"))[1]["id"]
    sfx = [{"suffix": "Schalten", "dpt": "DPST-1-1"}]
    ok(client.post(f"/api/projects/{pid}/specials", json={"category_id": cat, "location": str(floor["id"]), "name": "Sonder", "suffixes": sfx}))
    ok(client.post(f"/api/projects/{pid}/specials", json={"category_id": cat, "location": "central", "name": "Zentral", "suffixes": sfx}))
    impact = ok(client.get(f"/api/floors/{floor['id']}/delete-impact"))
    assert impact["name"] == "Erdgeschoss (EG)"
    assert impact["rooms"] == 3 and impact["points"] == 13 and impact["specials"] == 1
    assert impact["actors_detached"] == 4
    ok(client.delete(f"/api/floors/{floor['id']}"))
    assert [s["name"] for s in ok(client.get(f"/api/projects/{pid}/specials"))] == ["Zentral"]


def test_project_delete_impact(client):
    pid = seed_musterhaus(client)
    impact = ok(client.get(f"/api/projects/{pid}/delete-impact"))
    assert impact["floors"] == 2 and impact["rooms"] == 6 and impact["points"] == 23 and impact["actors"] == 8


def test_open_points_numbered_after_grouping(client):
    from backend.db import get_db
    from backend.routers.clarification_list import open_clarifications_grouped
    pid = seed_musterhaus(client)
    rooms = ok(client.get(f"/api/projects/{pid}/tree"))["floors"][0]["rooms"]
    ok(client.post(f"/api/projects/{pid}/clarifications", json={"text": "A", "room_id": rooms[0]["id"]}))
    ok(client.post(f"/api/projects/{pid}/clarifications", json={"text": "B", "room_id": rooms[1]["id"]}))
    ok(client.post(f"/api/projects/{pid}/clarifications", json={"text": "C", "room_id": rooms[0]["id"]}))
    ok(client.post(f"/api/projects/{pid}/clarifications", json={"text": "D"}))
    with get_db() as db:
        groups = open_clarifications_grouped(db, pid)
    flat = [(label, e["nr"], e["text"]) for label, es in groups for e in es]
    assert [n for _, n, _ in flat] == [1, 2, 3, 4]
    assert flat[0][0] == "Allgemein" and flat[0][2] == "D"
