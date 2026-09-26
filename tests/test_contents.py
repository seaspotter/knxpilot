"""The "Inhalt" cards on the Pflichtenheft/Dokumentation tabs and the
inline "Vorschau" PDFs."""
from backend.routers.dokumentation import DOKU_CHAPTERS
from conftest import ok, seed_musterhaus


def by_title(sections):
    return {s["title"]: s for s in sections}


def test_pflichtenheft_contents(client):
    pid = seed_musterhaus(client)
    s = by_title(ok(client.get(f"/api/projects/{pid}/pflichtenheft-contents")))
    assert list(s) == ["Vorbemerkungen", "Stockwerk- und Raumverzeichnis", "Funktionen und Geräte je Raum",
                       "Zentral- und Allgemeinfunktionen", "Stückliste"]
    assert s["Stockwerk- und Raumverzeichnis"]["detail"] == "2 Geschosse · 6 Räume"
    assert s["Funktionen und Geräte je Raum"]["included"]
    assert s["Stückliste"]["included"] and "Gerätetypen" in s["Stückliste"]["detail"]


def test_dokumentation_contents_follow_chapter_spec_and_checklist(client):
    pid = seed_musterhaus(client)
    sections = ok(client.get(f"/api/projects/{pid}/dokumentation-contents"))
    assert [s["title"] for s in sections] == [title for _, title, _, _ in DOKU_CHAPTERS]
    s = by_title(sections)
    assert s["Gruppenadressen"] == {"title": "Gruppenadressen", "included": False,
                                   "detail": "aus (Setup → Dokumentation)", "warn": False}
    fc = s["Funktionscheckliste — Testergebnisse"]
    assert fc["included"] and fc["warn"] and fc["detail"].startswith("0 / ")
    total = int(fc["detail"].split("/ ")[1].split()[0])

    key = next(iter(ok(client.get(f"/api/rooms/{ok(client.get(f'/api/projects/{pid}/tree'))['floors'][0]['rooms'][0]['id']}/function-checklist")).values()))[0]["key"]
    ok(client.put(f"/api/projects/{pid}/checklist-status/{key}", json={"status": "ok", "note": ""}))
    fc = by_title(ok(client.get(f"/api/projects/{pid}/dokumentation-contents")))["Funktionscheckliste — Testergebnisse"]
    assert fc["detail"] == f"1 / {total} getestet"


def test_inline_preview_disposition(client):
    pid = seed_musterhaus(client)
    for doc in ("pflichtenheft", "dokumentation"):
        r = client.get(f"/api/projects/{pid}/export-{doc}.pdf?inline=1")
        assert r.status_code == 200 and r.headers["content-disposition"].startswith("inline;")
        assert client.get(f"/api/projects/{pid}/export-{doc}.pdf").headers["content-disposition"].startswith("attachment;")
