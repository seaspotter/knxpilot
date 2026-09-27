"""The project's manuals tab rendered server-side (htmx). Downloads are
mocked - no network in tests."""
import json

import pytest

from backend.routers import manuals
from conftest import ok, seed_musterhaus


@pytest.fixture
def project(client, monkeypatch):
    pid = seed_musterhaus(client)
    by_model = {d["model"]: d for d in ok(client.get("/api/actor-types"))}
    for model in ("AKS-2016.03", "AKD-0401.02"):
        ok(client.put(f"/api/actor-types/{by_model[model]['id']}/manual-url", json={"manual_url": f"https://example.com/{model}.pdf"}))

    def fake_fetch(url):
        if "AKD" in url:
            raise ValueError("Kein PDF - der Link führt vermutlich auf eine Webseite statt direkt auf das Handbuch.")
        return b"%PDF-1.4 test", "application/pdf"
    monkeypatch.setattr(manuals, "_fetch_manual_bytes", fake_fetch)
    return pid, by_model


def toast(response):
    return json.loads(response.headers["HX-Trigger"])["show-toast"]


def test_tab_lists_used_devices_with_links(client, project):
    pid, _ = project
    body = client.get(f"/hx/projects/{pid}/manuals").text
    assert "MDT AKS-2016.03" in body and "MDT AKD-0401.02" in body and body.count(">Herunterladen<") == 2


def test_fetch_one_view_delete(client, project):
    pid, by_model = project
    aks = by_model["AKS-2016.03"]["id"]
    body = client.post(f"/hx/projects/{pid}/manuals/{aks}/fetch").text
    assert "Ansehen" in body and body.count(">Herunterladen<") == 1
    file_id = next(m["file_id"] for m in ok(client.get(f"/api/projects/{pid}/manuals")) if m["device_type_id"] == aks)
    assert client.get(f"/api/project-manuals/{file_id}/view").content.startswith(b"%PDF")
    assert client.delete(f"/hx/project-manuals/{file_id}").text.count(">Herunterladen<") == 2
    assert client.delete(f"/hx/project-manuals/{file_id}").status_code == 404


def test_fetch_failure_is_reported(client, project):
    pid, by_model = project
    r = client.post(f"/hx/projects/{pid}/manuals/{by_model['AKD-0401.02']['id']}/fetch")
    assert r.status_code == 502 and "Kein PDF" in r.json()["detail"]


def test_fetch_all_reports_partial_failure(client, project):
    pid, _ = project
    r = client.post(f"/hx/projects/{pid}/manuals/fetch-all")
    t = toast(r)
    assert t["level"] == "warning" and "1 heruntergeladen, 1 fehlgeschlagen: MDT AKD-0401.02" == t["message"]
    assert "Ansehen" in r.text
