"""Gebäudestruktur tree drag & drop: moving/reordering rooms and floors (with
the GA-impact dry run) and placing a Verteiler in a room."""
from conftest import ok, seed_musterhaus


def tree(client, pid):
    return ok(client.get(f"/api/projects/{pid}/tree"))


def room_names(client, pid):
    return [[r["name"] for r in f["rooms"]] for f in tree(client, pid)["floors"]]


def test_dry_run_reports_ga_changes_and_changes_nothing(client):
    pid = seed_musterhaus(client, wire=False)
    eg, og = tree(client, pid)["floors"]
    flur = next(r for r in eg["rooms"] if r["name"] == "Flur")
    before_names = room_names(client, pid)
    before_gas = ok(client.get(f"/api/projects/{pid}/preview"))

    result = ok(client.post(f"/api/rooms/{flur['id']}/move", json={"floor_id": og["id"], "index": 0, "dry_run": True}))
    assert result["ga_changed"] > 0      # Flur's functions change Mittelgruppe
    assert result["exported"] is False   # never exported to ETS yet
    assert room_names(client, pid) == before_names
    assert ok(client.get(f"/api/projects/{pid}/preview")) == before_gas


def test_move_room_to_other_floor_at_position(client):
    pid = seed_musterhaus(client, wire=False)
    eg, og = tree(client, pid)["floors"]
    flur = next(r for r in eg["rooms"] if r["name"] == "Flur")
    ok(client.post(f"/api/rooms/{flur['id']}/move", json={"floor_id": og["id"], "index": 1}))
    assert room_names(client, pid) == [["Wohnzimmer", "Küche"], ["Schlafzimmer", "Flur", "Kinderzimmer", "Bad"]]
    # the room kept its functions
    flur_after = next(r for r in tree(client, pid)["floors"][1]["rooms"] if r["name"] == "Flur")
    assert len(flur_after["points"]) == len(flur["points"])


def test_reorder_rooms_and_floors(client):
    pid = seed_musterhaus(client, wire=False)
    eg, og = tree(client, pid)["floors"]
    kueche = next(r for r in eg["rooms"] if r["name"] == "Küche")
    ok(client.post(f"/api/rooms/{kueche['id']}/move", json={"index": 0}))
    assert room_names(client, pid)[0] == ["Küche", "Wohnzimmer", "Flur"]
    # no-op move (same place) changes no group address
    assert ok(client.post(f"/api/rooms/{kueche['id']}/move", json={"index": 0, "dry_run": True}))["ga_changed"] == 0

    ok(client.post(f"/api/floors/{og['id']}/move", json={"index": 0}))
    assert [f["name"] for f in tree(client, pid)["floors"]] == [og["name"], eg["name"]]


def test_move_rejects_floor_of_other_project(client):
    pid = seed_musterhaus(client, wire=False)
    other = seed_musterhaus(client, name="Anderes", wire=False)
    room = tree(client, pid)["floors"][0]["rooms"][0]
    foreign_floor = tree(client, other)["floors"][0]
    assert client.post(f"/api/rooms/{room['id']}/move", json={"floor_id": foreign_floor["id"], "index": 0}).status_code == 400


def test_exported_flag_after_ets_export(client):
    pid = seed_musterhaus(client, wire=False)
    client.get(f"/api/projects/{pid}/export.csv")
    eg, og = tree(client, pid)["floors"]
    result = ok(client.post(f"/api/rooms/{eg['rooms'][0]['id']}/move", json={"floor_id": og["id"], "index": 0, "dry_run": True}))
    assert result["exported"] is True


def test_verteiler_in_room_follows_room_and_shows_in_tree(client):
    pid = seed_musterhaus(client, wire=False)
    eg, og = tree(client, pid)["floors"]
    flur = next(r for r in eg["rooms"] if r["name"] == "Flur")
    vid = ok(client.post(f"/api/projects/{pid}/verteiler", json={"floor_id": eg["id"], "name": "UV EG"}))["id"]
    assert [v["name"] for v in tree(client, pid)["floors"][0]["verteiler"]] == ["UV EG"]

    ok(client.put(f"/api/verteiler/{vid}/location", json={"room_id": flur["id"]}))
    t = tree(client, pid)
    assert t["floors"][0]["verteiler"] == []
    assert [v["name"] for v in next(r for r in t["floors"][0]["rooms"] if r["name"] == "Flur")["verteiler"]] == ["UV EG"]

    # moving the room to the OG takes the Verteiler along
    ok(client.post(f"/api/rooms/{flur['id']}/move", json={"floor_id": og["id"], "index": 0}))
    v = next(v for v in ok(client.get(f"/api/projects/{pid}/verteiler")) if v["id"] == vid)
    assert (v["floor_id"], v["room_id"], v["room_name"]) == (og["id"], flur["id"], "Flur")

    # deleting the room keeps the Verteiler on its floor
    ok(client.delete(f"/api/rooms/{flur['id']}"))
    assert [v["name"] for v in tree(client, pid)["floors"][1]["verteiler"]] == ["UV EG"]

    # back to "whole floor" / validation
    ok(client.put(f"/api/verteiler/{vid}/location", json={"floor_id": eg["id"]}))
    assert [v["name"] for v in tree(client, pid)["floors"][0]["verteiler"]] == ["UV EG"]
    other = seed_musterhaus(client, name="Anderes", wire=False)
    foreign_room = tree(client, other)["floors"][0]["rooms"][0]
    assert client.put(f"/api/verteiler/{vid}/location", json={"room_id": foreign_room["id"]}).status_code == 400


def test_verteilerplanung_pdf_with_room(client):
    pid = seed_musterhaus(client, wire=False)
    room = tree(client, pid)["floors"][0]["rooms"][0]
    ok(client.post(f"/api/projects/{pid}/verteiler", json={"room_id": room["id"], "name": "UV <Technik> & Co"}))
    r = client.get(f"/api/projects/{pid}/export-verteilerplanung.pdf")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_actor_list_follows_floor_order(client):
    pid = seed_musterhaus(client)
    eg, og = tree(client, pid)["floors"]
    at = ok(client.get("/api/actor-types"))[0]["id"]
    # added last, on the EG, and one without a Geschoss
    ok(client.post(f"/api/projects/{pid}/actor-instances", json={"actor_type_id": at, "floor_id": eg["id"]}))
    ok(client.post(f"/api/projects/{pid}/actor-instances", json={"actor_type_id": at}))
    floors = [a["floor_id"] for a in ok(client.get(f"/api/projects/{pid}/actor-instances"))]
    n_eg = floors.count(eg["id"])
    assert floors == [eg["id"]] * n_eg + [og["id"]] * floors.count(og["id"]) + [None]

    ok(client.post(f"/api/floors/{og['id']}/move", json={"index": 0}))
    floors = [a["floor_id"] for a in ok(client.get(f"/api/projects/{pid}/actor-instances"))]
    assert floors[0] == og["id"] and floors[-1] is None


def test_stueckliste_sorted_alphabetically_by_device(client):
    pid = seed_musterhaus(client)
    names = [d["device_name"] for d in ok(client.get(f"/api/projects/{pid}/device-summary"))]
    assert len(names) > 3
    assert names == sorted(names, key=str.casefold)
