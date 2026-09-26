"""The Klärungsliste tab rendered server-side (htmx): the /hx/... endpoints
return HTML fragments; the JSON API stays for badge/exports."""
import json

from backend.db import get_db
from backend.routers.klaerungsliste import open_klaerungen_grouped, open_klaerungen_text
from conftest import ok, seed_musterhaus


def html(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    return response.text


def badge(response):
    return json.loads(response.headers["HX-Trigger"])["klaerungen-changed"]


def test_tab_renders_form_and_list(client):
    pid = seed_musterhaus(client)
    body = html(client.get(f"/hx/projects/{pid}/klaerungsliste"))
    assert "Neuer Eintrag" in body and "Erdgeschoss (EG) — Wohnzimmer" in body   # room picker
    assert "Noch keine Einträge" in body


def test_create_status_answer_delete_roundtrip(client):
    pid = seed_musterhaus(client)
    room = ok(client.get(f"/api/projects/{pid}/tree"))["floors"][0]["rooms"][0]
    point = room["points"][0]

    r = client.post(f"/hx/projects/{pid}/klaerungen",
                    data={"text": "Spots dimmbar?", "typ": "Frage", "room_id": str(room["id"]), "room_point_id": str(point["id"])})
    body = html(r)
    assert "Spots dimmbar?" in body and "Erdgeschoss (EG) — Wohnzimmer" in body and point["label"] in body
    assert badge(r) == {"open": 1, "aged": 0}
    k = ok(client.get(f"/api/projects/{pid}/klaerungen"))[0]
    assert (k["room_id"], k["room_point_id"], k["status"]) == (room["id"], point["id"], "offen")

    r = client.post(f"/hx/klaerungen/{k['id']}/status", data={"status": "geklärt"})
    assert "status-geklaert" in html(r) and badge(r) == {"open": 0, "aged": 0}
    assert client.post(f"/hx/klaerungen/{k['id']}/status", data={"status": "egal"}).status_code == 400

    r = client.post(f"/hx/klaerungen/{k['id']}/antwort", data={"antwort": " Ja, alle "})
    assert 'hx-swap-oob="true"' in html(r)
    assert ok(client.get(f"/api/projects/{pid}/klaerungen"))[0]["antwort"] == "Ja, alle"

    r = client.delete(f"/hx/klaerungen/{k['id']}")
    assert "Noch keine Einträge" in html(r)
    assert client.post(f"/hx/klaerungen/{k['id']}/status", data={"status": "offen"}).status_code == 404


def test_edit_form_and_update(client):
    pid = seed_musterhaus(client)
    client.post(f"/hx/projects/{pid}/klaerungen", data={"text": "Alt", "typ": "Notiz"})
    k = ok(client.get(f"/api/projects/{pid}/klaerungen"))[0]
    form = html(client.get(f"/hx/klaerungen/{k['id']}/edit"))
    assert "Eintrag bearbeiten" in form and 'value="Alt"' in form and "<option selected>Notiz</option>" in form

    client.post(f"/hx/klaerungen/{k['id']}/status", data={"status": "abgelehnt"})
    html(client.put(f"/hx/klaerungen/{k['id']}", data={"text": "Neu", "typ": "Aufgabe", "room_id": ""}))
    k = ok(client.get(f"/api/projects/{pid}/klaerungen"))[0]
    assert (k["text"], k["typ"], k["status"], k["room_id"]) == ("Neu", "Aufgabe", "abgelehnt", None)  # status kept
    assert client.put(f"/hx/klaerungen/{k['id']}", data={"text": "  "}).status_code == 400


def test_points_picker(client):
    pid = seed_musterhaus(client)
    room = ok(client.get(f"/api/projects/{pid}/tree"))["floors"][0]["rooms"][0]
    body = html(client.get(f"/hx/klaerungsliste/points?room_id={room['id']}"))
    assert 'name="room_point_id"' in body and body.count("<option") == len(room["points"]) + 1
    assert "<select" not in html(client.get("/hx/klaerungsliste/points?room_id="))


def test_user_text_is_escaped(client):
    pid = seed_musterhaus(client)
    body = html(client.post(f"/hx/projects/{pid}/klaerungen", data={"text": "<script>alert(1)</script> & \"x\""}))
    assert "<script>alert(1)</script>" not in body and "&lt;script&gt;" in body


def test_open_text_matches_pdf_numbering(client):
    pid = seed_musterhaus(client)
    rooms = ok(client.get(f"/api/projects/{pid}/tree"))["floors"][0]["rooms"]
    for text, room in (("A", rooms[1]), ("B", None), ("C", rooms[0])):
        client.post(f"/hx/projects/{pid}/klaerungen", data={"text": text, "room_id": str(room["id"]) if room else ""})
    with get_db() as db:
        text = open_klaerungen_text(db, pid)
        groups = open_klaerungen_grouped(db, pid)
    numbered = [f"{e['nr']}. [Frage] {e['text']}" for _, entries in groups for e in entries]
    assert [line for line in text.splitlines() if line[:1].isdigit()] == numbered
    assert text.splitlines()[2] == "Allgemein"   # Allgemein first, like the PDF
