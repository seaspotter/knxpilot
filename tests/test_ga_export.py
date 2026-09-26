"""The ETS CSV is the product's core output - format rules from real ETS6
exports, plus a golden file so any unintended change in addressing shows up.
Regenerate the golden file deliberately with:
    KNXPILOT_UPDATE_GOLDEN=1 pytest tests/test_ga_export.py
"""
import csv
import io
import os
from pathlib import Path

from conftest import seed_musterhaus

GOLDEN = Path(__file__).parent / "fixtures" / "musterhaus_ga.csv"


def export(client, pid):
    r = client.get(f"/api/projects/{pid}/export.csv")
    assert r.status_code == 200
    return r.content


def test_csv_format_matches_ets6(client):
    pid = seed_musterhaus(client)
    raw = export(client, pid)
    text = raw.decode("iso-8859-1")
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
    assert rows[0] == ["Main", "Middle", "Sub", "Address", "Central", "Unfiltered", "Description", "DatapointType", "Security"]
    first_line = text.splitlines()[1]
    assert first_line.startswith('"') and '\t' in first_line  # every field quoted, tab-separated
    subs = [r for r in rows[1:] if r[2]]
    assert subs, "no group addresses exported"
    for r in rows[1:]:
        assert r[8] == "Auto"
        main, middle, sub = r[3].split("/")
        assert main.isdigit()
    for r in subs:
        assert r[7] == "" or r[7].startswith("DPST-"), r
    assert len({r[3] for r in subs}) == len(subs), "duplicate group addresses"
    assert "Wohnzimmer Decke Spots" in text and "Küche" in text  # umlauts survive iso-8859-1


def test_csv_matches_golden_file(client):
    pid = seed_musterhaus(client)
    raw = export(client, pid)
    if os.environ.get("KNXPILOT_UPDATE_GOLDEN"):
        GOLDEN.write_bytes(raw)
    assert GOLDEN.exists(), "golden file missing - create it with KNXPILOT_UPDATE_GOLDEN=1"
    assert raw == GOLDEN.read_bytes(), "GA export changed - if intended, regenerate the golden file (see module docstring)"


def test_changes_since_last_ets_export(client):
    from conftest import ok
    pid = seed_musterhaus(client)
    assert ok(client.get(f"/api/projects/{pid}/ga-changes"))["exported_at"] is None
    export(client, pid)  # the CSV download becomes the baseline
    c = ok(client.get(f"/api/projects/{pid}/ga-changes"))
    assert c["exported_at"] and not (c["added"] or c["removed"] or c["changed"] or c["moved"])

    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    kueche = next(r for f in tree["floors"] for r in f["rooms"] if r["name"] == "Küche")
    pts = {p["name"]: p["id"] for p in ok(client.get("/api/point-types"))}
    licht = next(v for k, v in pts.items() if k.startswith("Licht (Schalten)"))
    ok(client.post(f"/api/rooms/{kueche['id']}/points", json={"point_type_id": licht, "label": "Insel"}))
    c = ok(client.get(f"/api/projects/{pid}/ga-changes"))
    touched = [r["name"] for r in c["added"]] + [r["name"] for r in c["changed"]]
    assert any("Küche Insel" in n for n in touched), c

    ok(client.post(f"/api/projects/{pid}/ga-snapshot"))
    c = ok(client.get(f"/api/projects/{pid}/ga-changes"))
    assert not (c["added"] or c["removed"] or c["changed"] or c["moved"])


def test_removed_function_is_reported(client):
    from conftest import ok
    pid = seed_musterhaus(client)
    export(client, pid)
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    flur = next(r for f in tree["floors"] for r in f["rooms"] if r["name"] == "Flur")
    heiz = next(p for p in flur["points"] if not p["label"])  # Flur's only unlabeled point is its Heizkreis
    ok(client.delete(f"/api/room-points/{heiz['id']}"))
    c = ok(client.get(f"/api/projects/{pid}/ga-changes"))
    assert c["removed"] or c["changed"], c


def test_shifted_functions_are_reported_as_moves(client):
    """Adding a function shifts every later address in its floor block -
    those must show up as moves (change the address in ETS, keeping device
    links), not as a wall of renames."""
    from conftest import ok
    pid = seed_musterhaus(client)
    export(client, pid)
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    kueche = next(r for f in tree["floors"] for r in f["rooms"] if r["name"] == "Küche")
    pts = {p["name"]: p["id"] for p in ok(client.get("/api/point-types"))}
    licht = next(v for k, v in pts.items() if k.startswith("Licht (Schalten)"))
    ok(client.post(f"/api/rooms/{kueche['id']}/points", json={"point_type_id": licht, "label": "Insel"}))
    c = ok(client.get(f"/api/projects/{pid}/ga-changes"))
    moved = {m["name"]: (m["old_address"], m["address"]) for m in c["moved"]}
    assert "Flur Decke Schalten" in moved and moved["Flur Decke Schalten"][0] != moved["Flur Decke Schalten"][1]
    assert not any(r["old_name"].startswith("Flur Decke Schalten") for r in c["changed"])
    assert any(r["name"] == "Küche Insel Schalten" for r in c["added"])
    targets = [tuple(int(x) for x in m["address"].split("/")) for m in c["moved"]]
    assert targets == sorted(targets, reverse=True)  # highest first = collision-free order in ETS


def test_renamed_room_is_a_change_not_a_move(client):
    from conftest import ok
    pid = seed_musterhaus(client)
    export(client, pid)
    bad = next(r for f in ok(client.get(f"/api/projects/{pid}/tree"))["floors"] for r in f["rooms"] if r["name"] == "Bad")
    ok(client.put(f"/api/rooms/{bad['id']}", json={"name": "Badezimmer"}))
    c = ok(client.get(f"/api/projects/{pid}/ga-changes"))
    assert not c["moved"] and not c["added"] and not c["removed"]
    assert any(r["old_name"] == "Bad Spiegel Schalten" and r["name"] == "Badezimmer Spiegel Schalten" for r in c["changed"])
