"""Optional KNX lines: per-line PA numbering, coupler on .0, overview hints,
and lines surviving duplicate/backup."""
from conftest import ok, seed_musterhaus


def addresses(client, pid):
    ai = {a["id"]: a["physical_address"] for a in ok(client.get(f"/api/projects/{pid}/actor-instances"))}
    rd = []
    for f in ok(client.get(f"/api/projects/{pid}/tree"))["floors"]:
        for r in f["rooms"]:
            rd += [d["physical_address"] for d in ok(client.get(f"/api/rooms/{r['id']}/devices"))]
    return ai, rd


def two_apartments(client):
    pid = seed_musterhaus(client, wire=False)
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    eg, og = tree["floors"]
    l1 = ok(client.post(f"/api/projects/{pid}/lines", json={"area": 1, "line": 1, "name": "Wohnung EG"}))["id"]
    l2 = ok(client.post(f"/api/projects/{pid}/lines", json={"area": 1, "line": 2, "name": "Wohnung OG"}))["id"]
    ok(client.put(f"/api/floors/{eg['id']}/line", json={"line_id": l1}))
    ok(client.put(f"/api/floors/{og['id']}/line", json={"line_id": l2}))
    return pid, eg, og, l1, l2


def test_without_lines_everything_uses_the_prefix(client):
    pid = seed_musterhaus(client, wire=False)
    ok(client.post(f"/api/projects/{pid}/assign-physical-addresses", json={"prefix": "1.1"}))
    ai, rd = addresses(client, pid)
    assert all(a.startswith("1.1.") for a in list(ai.values()) + rd)
    assert ok(client.get(f"/api/projects/{pid}/lines")) == []


def test_each_line_numbered_separately(client):
    pid, eg, og, l1, l2 = two_apartments(client)
    ok(client.post(f"/api/projects/{pid}/assign-physical-addresses", json={"prefix": "9.9"}))  # prefix ignored with lines
    actors = ok(client.get(f"/api/projects/{pid}/actor-instances"))
    for a in actors:
        expected = "1.1." if a["floor_id"] == eg["id"] else "1.2."
        assert a["physical_address"].startswith(expected), a
    # both lines start their actuator block at .10 independently
    assert {a["physical_address"] for a in actors} >= {"1.1.10", "1.2.10"}


def test_room_and_actor_override_floor_line(client):
    pid, eg, og, l1, l2 = two_apartments(client)
    bad = next(r for r in og["rooms"] if r["name"] == "Bad")
    ok(client.put(f"/api/rooms/{bad['id']}/line", json={"line_id": l1}))  # e.g. apartment spans floors
    actor = ok(client.get(f"/api/projects/{pid}/actor-instances"))[-1]    # an OG actuator
    ok(client.put(f"/api/actor-instances/{actor['id']}/line", json={"line_id": l1}))
    ok(client.post(f"/api/projects/{pid}/assign-physical-addresses", json={"prefix": "1.1"}))
    assert all(d["physical_address"].startswith("1.1.") for d in ok(client.get(f"/api/rooms/{bad['id']}/devices")))
    assert next(a for a in ok(client.get(f"/api/projects/{pid}/actor-instances")) if a["id"] == actor["id"])["physical_address"].startswith("1.1.")


def test_line_coupler_gets_dot_zero_and_overview_hints(client):
    pid, eg, og, l1, l2 = two_apartments(client)
    lines = {l["address"]: l for l in ok(client.get(f"/api/projects/{pid}/lines"))}
    assert "Kein Linienkoppler geplant" in lines["1.2"]["warnings"]
    assert "Keine Busspannungsversorgung geplant" in lines["1.2"]["warnings"]
    types = {a["model"]: a["id"] for a in ok(client.get("/api/actor-types"))}
    for model in ("KNX TP Secure Coupler", "1477020"):  # Enertex coupler, Phoenix power supply
        ok(client.post(f"/api/projects/{pid}/actor-instances", json={"actor_type_id": types[model], "floor_id": og["id"]}))
    lines = {l["address"]: l for l in ok(client.get(f"/api/projects/{pid}/lines"))}
    assert lines["1.2"]["coupler_count"] == 1 and lines["1.2"]["power_supply_count"] == 1
    assert not any("Linienkoppler" in w or "Busspannung" in w for w in lines["1.2"]["warnings"])
    ok(client.post(f"/api/projects/{pid}/assign-physical-addresses", json={"prefix": "1.1"}))
    coupler = next(a for a in ok(client.get(f"/api/projects/{pid}/actor-instances")) if a["actor_type_name"].endswith("Coupler"))
    assert coupler["physical_address"] == "1.2.0"


def test_line_validation(client):
    pid, eg, og, l1, l2 = two_apartments(client)
    assert client.post(f"/api/projects/{pid}/lines", json={"area": 1, "line": 2}).status_code == 400   # duplicate
    assert client.post(f"/api/projects/{pid}/lines", json={"area": 16, "line": 1}).status_code == 400  # out of range
    other = seed_musterhaus(client, name="Anderes", wire=False)
    other_floor = ok(client.get(f"/api/projects/{other}/tree"))["floors"][0]
    assert client.put(f"/api/floors/{other_floor['id']}/line", json={"line_id": l1}).status_code == 400


def test_deleting_a_line_falls_back_to_inheriting(client):
    pid, eg, og, l1, l2 = two_apartments(client)
    ok(client.delete(f"/api/lines/{l2}"))
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    assert tree["floors"][1]["line_id"] is None


def test_duplicate_keeps_lines_and_assignments(client):
    pid, eg, og, l1, l2 = two_apartments(client)
    bad = next(r for r in og["rooms"] if r["name"] == "Bad")
    ok(client.put(f"/api/rooms/{bad['id']}/line", json={"line_id": l1}))
    new = ok(client.post(f"/api/projects/{pid}/duplicate"))["id"]
    new_lines = {l["id"]: l["address"] for l in ok(client.get(f"/api/projects/{new}/lines"))}
    assert sorted(new_lines.values()) == ["1.1", "1.2"]
    tree = ok(client.get(f"/api/projects/{new}/tree"))
    assert [new_lines[f["line_id"]] for f in tree["floors"]] == ["1.1", "1.2"]
    new_bad = next(r for r in tree["floors"][1]["rooms"] if r["name"] == "Bad")
    assert new_lines[new_bad["line_id"]] == "1.1"
