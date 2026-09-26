import pytest

from backend.routers.zeiterfassung import _snapped_range
from conftest import ok


def hm(iso):
    return iso[11:16]


@pytest.mark.parametrize("grid,start,end,expected", [
    (15, "12:04:00", "12:55:00", ("12:00", "13:00")),
    (15, "12:04:20", "12:06:10", ("12:00", "12:15")),   # min one grid step
    (15, "12:14:00", "12:52:00", ("12:15", "12:45")),
    (30, "12:14:00", "12:52:00", ("12:00", "13:00")),
    (30, "12:04:00", "12:06:00", ("12:00", "12:30")),
    (1, "12:04:20", "12:06:10", ("12:04", "12:06")),
])
def test_snapping(grid, start, end, expected):
    s, e = _snapped_range(f"2026-09-26T{start}Z", f"2026-09-26T{end}Z", grid)
    assert (hm(s), hm(e)) == expected


@pytest.fixture
def pid(client):
    return ok(client.post("/api/projects", json={"name": "P"}))["id"]


def entries(client):
    return ok(client.get("/api/time-entries"))


def set_rounding(client, minutes, enabled=True):
    cp = ok(client.get("/api/company-profile"))
    cp.update(zeiterfassung_rounding_minutes=minutes, zeiterfassung_enabled=enabled)
    ok(client.put("/api/company-profile", json=cp))


def test_timer_start_stop_and_double_start(client, pid):
    ok(client.post("/api/time-entries/start", json={"project_id": pid}))
    assert client.post("/api/time-entries/start", json={"project_id": pid}).status_code == 409
    ok(client.post("/api/time-entries/stop"))
    [e] = entries(client)
    assert e["ended_at"] and e["billed_minutes"] == 15


def test_disabled_refuses_start(client, pid):
    set_rounding(client, 15, enabled=False)
    assert client.post("/api/time-entries/start", json={"project_id": pid}).status_code == 400


def test_invalid_rounding_rejected(client):
    cp = ok(client.get("/api/company-profile"))
    cp["zeiterfassung_rounding_minutes"] = 7
    assert client.put("/api/company-profile", json=cp).status_code == 400


def test_edit_keeps_unchanged_times_after_grid_change(client, pid):
    e = ok(client.post("/api/time-entries", json={"project_id": pid, "started_at": "2026-09-25T10:15:00Z",
                                                   "ended_at": "2026-09-25T10:45:00Z"}))["id"]
    set_rounding(client, 30)
    [cur] = entries(client)
    ok(client.put(f"/api/time-entries/{e}", json={"project_id": pid, "started_at": cur["started_at"],
                                                   "ended_at": cur["ended_at"], "note": "nur Notiz"}))
    [cur] = entries(client)
    assert (hm(cur["started_at"]), hm(cur["ended_at"]), cur["billed_minutes"]) == ("10:15", "10:45", 30)
    ok(client.put(f"/api/time-entries/{e}", json={"project_id": pid, "started_at": "2026-09-25T10:14:00Z",
                                                   "ended_at": cur["ended_at"]}))
    [cur] = entries(client)
    assert (hm(cur["started_at"]), hm(cur["ended_at"])) == ("10:00", "11:00")  # changed times do snap


def test_entries_of_deleted_project_stay_editable(client, pid):
    e = ok(client.post("/api/time-entries", json={"project_id": pid, "started_at": "2026-09-25T10:00:00Z",
                                                   "ended_at": "2026-09-25T11:00:00Z"}))["id"]
    ok(client.delete(f"/api/projects/{pid}"))
    [cur] = entries(client)
    assert cur["project_name"] == "P"
    ok(client.put(f"/api/time-entries/{e}", json={"project_id": pid, "started_at": cur["started_at"],
                                                   "ended_at": cur["ended_at"], "note": "danach"}))
    assert entries(client)[0]["note"] == "danach"
    assert client.put(f"/api/time-entries/{e}", json={"project_id": 99999, "started_at": cur["started_at"],
                                                       "ended_at": cur["ended_at"]}).status_code == 404


def test_invoiced_flag_and_filter(client, pid):
    ids = [ok(client.post("/api/time-entries", json={"project_id": pid, "started_at": f"2026-09-2{d}T08:00:00Z",
                                                      "ended_at": f"2026-09-2{d}T09:00:00Z"}))["id"] for d in (1, 2, 3)]
    ok(client.put("/api/time-entries/invoiced", json={"ids": ids[:2], "invoiced": True}))
    assert len(ok(client.get("/api/time-entries", params={"invoiced": "false"}))) == 1
    assert len(ok(client.get("/api/time-entries", params={"invoiced": "true"}))) == 2
