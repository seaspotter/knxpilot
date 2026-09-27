"""The "Inhalt" cards on the Pflichtenheft/Dokumentation tabs and the
inline "Vorschau" PDFs."""
from backend.routers.documentation import DOCUMENTATION_CHAPTERS
from conftest import ok, seed_musterhaus


def by_title(sections):
    return {s["title"]: s for s in sections}


def test_pflichtenheft_contents(client):
    pid = seed_musterhaus(client)
    s = by_title(ok(client.get(f"/api/projects/{pid}/specification-contents")))
    assert list(s) == ["Vorbemerkungen", "Stockwerk- und Raumverzeichnis", "Funktionen und Geräte je Raum",
                       "Zentral- und Allgemeinfunktionen", "Stückliste"]
    assert s["Stockwerk- und Raumverzeichnis"]["detail"] == "2 Geschosse · 6 Räume"
    assert s["Funktionen und Geräte je Raum"]["included"]
    assert s["Stückliste"]["included"] and "Gerätetypen" in s["Stückliste"]["detail"]


def test_dokumentation_contents_follow_chapter_spec_and_checklist(client):
    pid = seed_musterhaus(client)
    sections = ok(client.get(f"/api/projects/{pid}/documentation-contents"))
    assert [s["title"] for s in sections] == [title for _, title, _, _ in DOCUMENTATION_CHAPTERS]
    s = by_title(sections)
    assert s["Gruppenadressen"] == {"title": "Gruppenadressen", "included": False,
                                   "detail": "aus (Setup → Dokumentation)", "warn": False}
    fc = s["Funktionscheckliste — Testergebnisse"]
    assert fc["included"] and fc["warn"] and fc["detail"].startswith("0 / ")
    total = int(fc["detail"].split("/ ")[1].split()[0])

    key = next(iter(ok(client.get(f"/api/rooms/{ok(client.get(f'/api/projects/{pid}/tree'))['floors'][0]['rooms'][0]['id']}/function-checklist")).values()))[0]["key"]
    ok(client.put(f"/api/projects/{pid}/checklist-status/{key}", json={"status": "ok", "note": ""}))
    fc = by_title(ok(client.get(f"/api/projects/{pid}/documentation-contents")))["Funktionscheckliste — Testergebnisse"]
    assert fc["detail"] == f"1 / {total} getestet · Unterschrift Systemintegrator fehlt"

    # tick date is kept per item
    status = ok(client.get(f"/api/projects/{pid}/checklist-status"))[key]
    assert status["status"] == "ok" and status["updated_at"]

    # Funktionscheckliste signature (own role, separate from the Übergabe's)
    png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    ok(client.put(f"/api/projects/{pid}/signatures/fc_systemintegrator", json={"image": png}))
    s = by_title(ok(client.get(f"/api/projects/{pid}/documentation-contents")))
    assert s["Funktionscheckliste — Testergebnisse"]["detail"].endswith("· unterschrieben")
    assert "0 / 2 Unterschriften" in s["Übergabe-Checkliste — Ergebnisse"]["detail"]
    for doc in ("funktionscheckliste", "documentation"):
        r = client.get(f"/api/projects/{pid}/export-{doc}.pdf")
        assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_inline_preview_disposition(client):
    pid = seed_musterhaus(client)
    for doc in ("specification", "documentation"):
        r = client.get(f"/api/projects/{pid}/export-{doc}.pdf?inline=1")
        assert r.status_code == 200 and r.headers["content-disposition"].startswith("inline;")
        assert client.get(f"/api/projects/{pid}/export-{doc}.pdf").headers["content-disposition"].startswith("attachment;")


def test_local_time_text():
    from backend.utils import local_time_text
    assert local_time_text("") == "" and local_time_text("kaputt") == ""
    assert len(local_time_text("2026-09-26 12:32:05")) == len("26.09.2026 14:32")
    assert local_time_text("2026-09-26T12:32:05+00:00").startswith("26.09.2026")
