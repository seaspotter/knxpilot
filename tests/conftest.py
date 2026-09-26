"""
Shared test setup. Every test gets a brand-new SQLite database in a temp
directory (KNXPILOT_DB_PATH / backend.db.DB_PATH), so the suite never
touches the real backend/data/knx_ga.db and tests can't leak state into
each other.
"""
import os
import tempfile
from pathlib import Path

# Must happen before anything imports backend.main, which runs init_db() at
# import time against whatever DB_PATH is then.
_SESSION_DIR = Path(tempfile.mkdtemp(prefix="knxpilot-tests-"))
os.environ["KNXPILOT_DB_PATH"] = str(_SESSION_DIR / "import-time.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import backend.backup  # noqa: E402
import backend.db  # noqa: E402
from backend.main import app  # noqa: E402


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "knx_ga.db"
    monkeypatch.setattr(backend.db, "DB_PATH", path)
    monkeypatch.setattr(backend.backup, "DB_PATH", path)
    return path


@pytest.fixture
def client(db_path):
    backend.db.init_db()
    with TestClient(app) as c:
        yield c


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def seed_musterhaus(client, name="Musterhaus"):
    """A small but complete demo project: 2 floors, 6 rooms, 23 functions,
    devices, actuators with auto-assigned channels and physical addresses.
    Deterministic, so its GA CSV can serve as a golden file."""
    pid = ok(client.post("/api/projects", json={"name": name, "customer": "Familie Muster", "location": "Musterstadt"}))["id"]
    pts = {p["name"]: p["id"] for p in ok(client.get("/api/point-types"))}
    pt = lambda prefix: next(v for k, v in pts.items() if k.startswith(prefix))
    at = {a["model"]: a["id"] for a in ok(client.get("/api/actor-types"))}
    plan = {
        "Erdgeschoss (EG)": {
            "Wohnzimmer": [("Licht (Dimmen)", "Decke Spots", True), ("Licht (Dimmen)", "Stehleuchte"), ("Steckdose", "Sofa"),
                           ("Heizkreis", ""), ("Jalousie", "Fenster Süd"), ("Jalousie", "Terrassentür")],
            "Küche": [("Licht (Schalten)", "Decke"), ("Licht (Dimmen)", "Arbeitsfläche"), ("Steckdose", "Kaffeemaschine"),
                      ("Heizkreis", ""), ("Jalousie", "Fenster West")],
            "Flur": [("Licht (Schalten)", "Decke", True), ("Heizkreis", "")],
        },
        "Obergeschoss (OG)": {
            "Schlafzimmer": [("Licht (Dimmen)", "Decke"), ("Licht (Schalten)", "Nachttisch"), ("Heizkreis", ""), ("Jalousie", "Fenster Ost")],
            "Kinderzimmer": [("Licht (Schalten)", "Decke"), ("Heizkreis", ""), ("Jalousie", "Fenster Süd")],
            "Bad": [("Licht (Schalten)", "Spiegel"), ("Licht (Dimmen)", "Decke Spots", True), ("Heizkreis", "")],
        },
    }
    devices = {"Wohnzimmer": ["BE-GT2TW.02", "SCN-BWM63.02"], "Küche": ["BE-TAL63T2.01"], "Flur": ["SCN-BWM63.02"],
               "Schlafzimmer": ["BE-GT2TW.02"], "Kinderzimmer": ["BE-TAL63T2.01"], "Bad": ["SCN-BWM63T.02"]}
    floor_ids = []
    for fname, rooms in plan.items():
        fid = ok(client.post(f"/api/projects/{pid}/floors", json={"name": fname}))["id"]
        floor_ids.append(fid)
        for rname, points in rooms.items():
            rid = ok(client.post(f"/api/floors/{fid}/rooms", json={"name": rname}))["id"]
            for p in points:
                ok(client.post(f"/api/rooms/{rid}/points", json={"point_type_id": pt(p[0]), "label": p[1], "has_bwm": len(p) > 2}))
            for m in devices.get(rname, []):
                ok(client.post(f"/api/rooms/{rid}/devices", json={"device_type_id": at[m]}))
    for fid in floor_ids:
        for m in ["AKS-2016.03", "AKD-0401.02", "AKH-0800.03", "JAL-0810M.02"]:
            ok(client.post(f"/api/projects/{pid}/actor-instances", json={"actor_type_id": at[m], "floor_id": fid, "location_label": "Verteilung"}))
    ok(client.post(f"/api/projects/{pid}/circuits/auto-assign"))
    ok(client.post(f"/api/projects/{pid}/assign-physical-addresses", json={"prefix": "1.1"}))
    return pid
