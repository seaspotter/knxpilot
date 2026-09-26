"""Device catalog tab rendered server-side (htmx): add/edit/delete with the
group-dependent fields, search, manual URLs, and the in-use safeguards."""
import json

from conftest import ok, seed_musterhaus


def devices(client):
    return ok(client.get("/api/actor-types"))


def changed(response):
    assert response.status_code == 200, response.text
    assert json.loads(response.headers["HX-Trigger"])["catalog-changed"] is True
    return response.text


def test_tab_and_search(client):
    body = client.get("/hx/device-catalog").text
    assert 'hx-post="/hx/device-catalog"' in body and "<h4" in body   # grouped list
    hits = client.get("/hx/device-catalog/list?q=AKS-2016").text
    assert "AKS-2016.03" in hits and "BE-GT2TW" not in hits and "von" in hits
    assert "Keine Geräte gefunden" in client.get("/hx/device-catalog/list?q=gibtesnicht").text


def test_add_actuator_and_custom_group(client):
    body = changed(client.post("/hx/device-catalog", data={
        "manufacturer": "Test & Co", "model": "X-1 <neu>", "group_name": "Aktor", "channel_type": "Schalten",
        "channel_count": "12", "width_te": "4", "description": "Testaktor", "q": ""}))
    assert "X-1 &lt;neu&gt;" in body
    d = next(d for d in devices(client) if d["model"] == "X-1 <neu>")
    assert (d["group_name"], d["channel_type"], d["channel_count"], d["width_te"]) == ("Aktor", "Schalten", 12, 4)
    changed(client.post("/hx/device-catalog", data={
        "model": "S-1", "group_name": "__custom__", "group_custom": "Präsenzmelder", "channel_type": "ignored", "channel_count": "5"}))
    s = next(d for d in devices(client) if d["model"] == "S-1")
    assert (s["group_name"], s["channel_type"], s["channel_count"]) == ("Präsenzmelder", "", None)   # actuator fields dropped


def test_validation(client):
    assert client.post("/hx/device-catalog", data={"model": " ", "group_name": "Sensor"}).status_code == 400
    r = client.post("/hx/device-catalog", data={"model": "A-1", "group_name": "Aktor", "channel_type": ""})
    assert r.status_code == 400 and "Type" in r.json()["detail"]
    assert client.post("/hx/device-catalog", data={"model": "A-1", "group_name": "Sensor", "width_te": "vier"}).status_code == 400


def test_edit_keeps_manual_url_and_search(client):
    d = next(d for d in devices(client) if d["model"] == "AKS-2016.03")
    r = client.put(f"/hx/device-catalog/{d['id']}/manual-url", data={"manual_url": " https://example.com/aks.pdf "})
    assert r.status_code == 200 and json.loads(r.headers["HX-Trigger"])["catalog-changed"]
    form = client.get(f"/hx/device-catalog/{d['id']}/edit?q=AKS").text
    assert "Gerät bearbeiten" in form and 'value="AKS"' in form and 'data-group="Aktor"' in form
    body = changed(client.put(f"/hx/device-catalog/{d['id']}", data={
        "manufacturer": "MDT", "model": "AKS-2016.03", "group_name": "Aktor", "channel_type": "Schalten",
        "channel_count": "20", "description": "neu beschrieben", "q": "AKS"}))
    assert "neu beschrieben" in body and "BE-GT2TW" not in body   # search kept
    d = next(x for x in devices(client) if x["id"] == d["id"])
    assert (d["description"], d["manual_url"]) == ("neu beschrieben", "https://example.com/aks.pdf")


def test_delete_and_in_use_protection(client):
    pid = seed_musterhaus(client)
    used = next(d for d in devices(client) if d["model"] == "AKS-2016.03")   # an actuator in the demo project
    r = client.delete(f"/hx/device-catalog/{used['id']}")
    assert r.status_code == 400 and "verwendet" in r.json()["detail"]
    free = next(d for d in devices(client) if d["model"] == "SCN-IP000.03")
    ok(client.post(f"/api/floors/{ok(client.get(f'/api/projects/{pid}/tree'))['floors'][0]['id']}/devices",
                   json={"device_type_id": free["id"]}))   # now used as a floor device
    assert client.delete(f"/hx/device-catalog/{free['id']}").status_code == 400
    unused = next(d for d in devices(client) if d["model"] == "BE-TAS63T4.01")
    changed(client.delete(f"/hx/device-catalog/{unused['id']}"))
    assert all(d["id"] != unused["id"] for d in devices(client))


def test_clear_keeps_devices_in_use_incl_floor_devices(client):
    pid = seed_musterhaus(client)
    ip = next(d for d in devices(client) if d["model"] == "SCN-IP000.03")
    ok(client.post(f"/api/floors/{ok(client.get(f'/api/projects/{pid}/tree'))['floors'][0]['id']}/devices",
                   json={"device_type_id": ip["id"]}))
    r = client.delete("/hx/device-catalog")
    assert "in Verwendung übersprungen" in json.loads(r.headers["HX-Trigger"])["show-toast"]["message"]
    left = {d["model"] for d in devices(client)}
    assert "SCN-IP000.03" in left and "AKS-2016.03" in left   # floor device and actuator kept


def test_manuals_tab(client):
    body = client.get("/hx/device-catalog/manuals").text
    assert 'name="manual_url"' in body and "hx-put" in body
    assert "AKS-2016.03" in client.get("/hx/device-catalog/manuals/list?q=aks").text
