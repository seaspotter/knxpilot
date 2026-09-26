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
