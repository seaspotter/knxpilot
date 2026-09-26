"""Bulk actions show a preview first - it must not write anything and must
match what the real run then does."""
from conftest import ok, seed_musterhaus


def test_circuit_auto_assign_dry_run(client):
    pid = seed_musterhaus(client, wire=False)
    preview = ok(client.post(f"/api/projects/{pid}/circuits/auto-assign", params={"dry_run": "true"}))
    assert preview["assigned"] == 23 and len(preview["details"]) == 23
    assert not any(c["assignment"] for c in ok(client.get(f"/api/projects/{pid}/circuits")))  # nothing written
    real = ok(client.post(f"/api/projects/{pid}/circuits/auto-assign"))
    assert real["details"] == preview["details"]
    assert all(c["assignment"] for c in ok(client.get(f"/api/projects/{pid}/circuits")))


def test_physical_address_preview(client):
    pid = seed_musterhaus(client, wire=False)
    preview = ok(client.post(f"/api/projects/{pid}/assign-physical-addresses/preview", json={"prefix": "1.1"}))
    assert preview["assignments"] and all(a["address"].startswith("1.1.") and a["device"] and a["where"] for a in preview["assignments"])
    assert not any(ai["physical_address"] for ai in ok(client.get(f"/api/projects/{pid}/actor-instances")))
    real = ok(client.post(f"/api/projects/{pid}/assign-physical-addresses", json={"prefix": "1.1"}))
    assert real["assigned"] == len(preview["assignments"])


def test_catalog_import_preview(client):
    preview = ok(client.post("/api/actor-types/import-defaults/preview"))
    assert preview["new"] == [] and preview["changed"] == [] and preview["unchanged"] > 50  # fresh install = defaults
    types = ok(client.get("/api/actor-types"))
    at = next(a for a in types if a["model"] == "BE-GT2TW.02")
    ok(client.put(f"/api/actor-types/{at['id']}", json={**at, "description": "Meine eigene Beschreibung"}))
    gone = next(a for a in types if a["model"] == "SCN-BWM63.02")
    ok(client.delete(f"/api/actor-types/{gone['id']}"))
    preview = ok(client.post("/api/actor-types/import-defaults/preview"))
    assert any(n.endswith("SCN-BWM63.02") for n in preview["new"])
    [change] = [c for c in preview["changed"] if c["device"].endswith("BE-GT2TW.02")]
    assert change["changes"] == [{"field": "Beschreibung", "old": "Meine eigene Beschreibung", "new": at["description"]}]
    assert ok(client.get("/api/actor-types"))  # preview wrote nothing:
    assert next(a for a in ok(client.get("/api/actor-types")) if a["model"] == "BE-GT2TW.02")["description"] == "Meine eigene Beschreibung"


def test_catalog_preview_ignores_manual_url_when_absent(client):
    at = next(a for a in ok(client.get("/api/actor-types")) if a["model"] == "BE-GT2TW.02")
    ok(client.put(f"/api/actor-types/{at['id']}/manual-url", json={"manual_url": "https://example.com/m.pdf"}))
    preview = ok(client.post("/api/actor-types/import-defaults/preview"))
    assert not any(c["device"].endswith("BE-GT2TW.02") for c in preview["changed"])  # bundled files have no manual_url
