"""The time tracking tab rendered server-side (htmx): list/filters, the
entry dialog in the browser's time zone, and mutations that signal the list
to refresh."""
import json

import pytest

from conftest import ok

BERLIN = {"X-Timezone": "Europe/Berlin", "X-Timezone-Offset": "-120"}


@pytest.fixture
def pids(client):
    return [ok(client.post("/api/projects", json={"name": n}))["id"] for n in ("Haus A", "Haus B")]


def add(client, pid, start, end, note=""):
    return ok(client.post("/api/time-entries", json={"project_id": pid, "started_at": start, "ended_at": end, "note": note}))["id"]


def entries(client):
    return ok(client.get("/api/time-entries"))


def signals(response):
    assert response.status_code == 200, response.text
    return json.loads(response.headers["HX-Trigger"])


def test_tab_shows_entries_in_browser_time_and_totals(client, pids):
    add(client, pids[0], "2026-09-25T08:00:00Z", "2026-09-25T09:30:00Z", "Programmierung <ETS>")
    add(client, pids[1], "2026-09-25T10:00:00Z", "2026-09-25T10:15:00Z")
    body = client.get("/hx/time-tracking", headers=BERLIN).text
    assert "Fr., 25.09.2026" in body and "10:00" in body and "11:30" in body   # UTC+2
    assert "Summe je Projekt" in body and "1:30 h" in body and "0:15 h" in body and "Summe: 1:45 h" in body
    assert "&lt;ETS&gt;" in body                                                 # escaped
    assert "Haus A" in body and "Haus B" in body                                 # filter options


def test_filters(client, pids):
    a = add(client, pids[0], "2026-09-25T08:00:00Z", "2026-09-25T09:00:00Z")
    add(client, pids[1], "2026-09-25T10:00:00Z", "2026-09-25T11:00:00Z")
    ok(client.put("/api/time-entries/invoiced", json={"ids": [a], "invoiced": True}))
    only_a = client.get(f"/hx/time-tracking/list?project_id={pids[0]}").text
    assert "Summe je Projekt" not in only_a and only_a.count("<tr>") == 2   # header + 1 entry
    open_only = client.get("/hx/time-tracking/list?invoiced=0").text
    assert "Haus B" in open_only and "Haus A" not in open_only


def test_invoiced_toggle_and_mark_shown(client, pids):
    a = add(client, pids[0], "2026-09-25T08:00:00Z", "2026-09-25T09:00:00Z")
    add(client, pids[1], "2026-09-25T10:00:00Z", "2026-09-25T11:00:00Z")
    assert signals(client.post(f"/hx/time-tracking/entries/{a}/invoiced", data={"invoiced": "true"})) == {"time-entries-changed": True}
    assert [e["invoiced"] for e in entries(client) if e["id"] == a] == [True]
    signals(client.post("/hx/time-tracking/mark-invoiced", data={"project_id": str(pids[1]), "invoiced": ""}))
    assert all(e["invoiced"] for e in entries(client))


def test_new_entry_in_browser_time_snapped_and_closes_dialog(client, pids):
    form = client.get(f"/hx/time-tracking/entries/new?current_project={pids[1]}", headers=BERLIN).text
    assert "Eintrag nachtragen" in form and f'<option value="{pids[1]}" selected>' in form
    assert "<option>00:15</option>" in form and "<option>00:05</option>" not in form   # 15-min grid
    r = client.post("/hx/time-tracking/entries", headers=BERLIN,
                    data={"project_id": pids[0], "date": "2026-09-25", "start": "10:00", "end": "11:30", "note": " x "})
    assert signals(r) == {"time-entries-changed": True, "hx-modal-close": True}
    [e] = entries(client)
    assert (e["started_at"], e["ended_at"], e["note"]) == ("2026-09-25T08:00:00+00:00", "2026-09-25T09:30:00+00:00", "x")


def test_entry_past_midnight_and_validation(client, pids):
    client.post("/hx/time-tracking/entries", headers=BERLIN,
                data={"project_id": pids[0], "date": "2026-09-25", "start": "23:00", "end": "01:00"})
    [e] = entries(client)
    assert e["billed_minutes"] == 120
    bad = client.post("/hx/time-tracking/entries", data={"project_id": pids[0], "date": "2026-09-25", "start": "10:00", "end": "10:00"})
    assert bad.status_code == 400 and "Bis muss nach Von" in bad.json()["detail"]


def test_edit_keeps_off_grid_times_when_untouched(client, pids):
    set_min = ok(client.get("/api/company-profile"))
    set_min["time_tracking_rounding_minutes"] = 1
    ok(client.put("/api/company-profile", json=set_min))
    e = add(client, pids[0], "2026-09-25T08:07:00Z", "2026-09-25T08:52:00Z")
    set_min["time_tracking_rounding_minutes"] = 15
    ok(client.put("/api/company-profile", json=set_min))

    form = client.get(f"/hx/time-tracking/entries/{e}/edit", headers=BERLIN).text
    assert "Eintrag bearbeiten" in form and "<option selected>10:07</option>" in form   # off-grid time offered
    signals(client.put(f"/hx/time-tracking/entries/{e}", headers=BERLIN,
                       data={"project_id": pids[0], "date": "2026-09-25", "start": "10:07", "end": "10:52", "note": "nur Notiz"}))
    [row] = entries(client)
    assert (row["started_at"][11:16], row["ended_at"][11:16], row["note"]) == ("08:07", "08:52", "nur Notiz")


def test_delete(client, pids):
    e = add(client, pids[0], "2026-09-25T08:00:00Z", "2026-09-25T09:00:00Z")
    signals(client.delete(f"/hx/time-tracking/entries/{e}"))
    assert entries(client) == []
    assert "Noch keine Zeiten erfasst." in client.get("/hx/time-tracking/list").text
