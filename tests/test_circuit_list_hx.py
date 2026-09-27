"""Circuit list tab ("Abgangsliste" sub-tab) rendered server-side (htmx):
the channel-demand summary, actor-instance list/form and the per-channel
assignment selects, via the /hx/... endpoints in
backend/routers/circuit_list.py."""
from conftest import ok, seed_musterhaus


def html(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    return response.text


def test_tab_renders_summary_actors_and_circuits(client):
    pid = seed_musterhaus(client)
    body = html(client.get(f"/hx/projects/{pid}/circuit-list"))
    assert "Wohnzimmer" in body and "Erdgeschoss (EG)" in body
    assert "AKS-2016.03" in body or "belegt" in body
    circuits = ok(client.get(f"/api/projects/{pid}/circuits"))
    assert any(c["assignment"] for c in circuits)  # wired by seed_musterhaus


def test_tab_without_actors_shows_empty_state(client):
    pid = ok(client.post("/api/projects", json={"name": "Leer"}))["id"]
    body = html(client.get(f"/hx/projects/{pid}/circuit-list"))
    assert "Noch keine Aktoren hinzugefügt" in body


def _actor_type_id(client, group="Aktor"):
    return next(a["id"] for a in ok(client.get("/api/actor-types")) if a["group_name"] == group)


def test_add_edit_delete_actor_instance(client):
    pid = ok(client.post("/api/projects", json={"name": "Test"}))["id"]
    eg = ok(client.post(f"/api/projects/{pid}/floors", json={"name": "EG"}))["id"]
    actor_type_id = _actor_type_id(client)

    body = html(client.post(f"/hx/projects/{pid}/actor-instances",
                             data={"actor_type_id": actor_type_id, "floor_id": str(eg),
                                   "location_label": "UV Technik", "physical_address": "1.1.1"}))
    assert "UV Technik" in body and "1.1.1" in body
    ai_id = ok(client.get(f"/api/projects/{pid}/actor-instances"))[0]["id"]

    form = html(client.get(f"/hx/actor-instances/{ai_id}/edit"))
    assert 'value="1.1.1"' in form and "Änderungen speichern" in form

    body = html(client.put(f"/hx/actor-instances/{ai_id}", data={"floor_id": str(eg), "location_label": "Umgezogen", "physical_address": "1.1.2"}))
    assert "Umgezogen" in body and "1.1.2" in body
    ai = ok(client.get(f"/api/projects/{pid}/actor-instances"))[0]
    assert (ai["location_label"], ai["physical_address"]) == ("Umgezogen", "1.1.2")

    body = html(client.get(f"/hx/projects/{pid}/actor-instances/cancel-edit"))
    assert "+ Aktor hinzufügen" in body

    body = html(client.delete(f"/hx/actor-instances/{ai_id}"))
    assert "Noch keine Aktoren hinzugefügt" in body
    assert ok(client.get(f"/api/projects/{pid}/actor-instances")) == []


def test_assign_and_unassign_circuit_swaps_only_that_row(client):
    pid = seed_musterhaus(client, wire=False)
    circuits = ok(client.get(f"/api/projects/{pid}/circuits"))
    circuit = next(c for c in circuits if not c["assignment"])
    instances = ok(client.get(f"/api/projects/{pid}/actor-instances"))
    matching = next(ai for ai in instances if ai["channel_type"] == circuit["channel_type"])

    body = html(client.post("/hx/circuit-list/assign", data={
        "project_id": pid, "room_point_id": circuit["room_point_id"], "channel_seq": circuit["channel_seq"],
        "value": f"{matching['id']}|A",
    }))
    assert 'class="rc-row rc-row-3"' in body
    assert 'selected' in body
    updated = ok(client.get(f"/api/projects/{pid}/circuits"))
    assigned = next(c for c in updated if c["room_point_id"] == circuit["room_point_id"] and c["channel_seq"] == circuit["channel_seq"])
    assert assigned["assignment"]["actor_instance_id"] == matching["id"] and assigned["assignment"]["channel_letter"] == "A"

    body = html(client.post("/hx/circuit-list/assign", data={
        "project_id": pid, "room_point_id": circuit["room_point_id"], "channel_seq": circuit["channel_seq"], "value": "",
    }))
    assert 'class="rc-row rc-row-3"' in body
    updated = ok(client.get(f"/api/projects/{pid}/circuits"))
    assigned = next(c for c in updated if c["room_point_id"] == circuit["room_point_id"] and c["channel_seq"] == circuit["channel_seq"])
    assert assigned["assignment"] is None


def test_channel_summary_fragment(client):
    pid = seed_musterhaus(client)
    body = html(client.get(f"/hx/projects/{pid}/circuit-list/channel-summary"))
    assert "benötigt" in body and "zugeordnet" in body
