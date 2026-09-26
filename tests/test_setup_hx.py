"""Setup's settings pages rendered server-side (htmx): each page saves only
its own fields, validates, and answers with the page + a toast."""
import json

from conftest import ok


def profile(client):
    return ok(client.get("/api/company-profile"))


def saved(response):
    assert response.status_code == 200, response.text
    events = json.loads(response.headers["HX-Trigger"])
    assert events["company-profile-changed"] and events["show-toast"]["level"] == "success"
    return response.text


def test_every_page_renders(client):
    for section in ("company", "specification", "documentation", "email", "time-tracking", "backup"):
        r = client.get(f"/hx/setup/{section}")
        assert r.status_code == 200 and f'hx-post="/hx/setup/{section}"' in r.text, section
    assert client.get("/hx/setup/unknown").status_code == 404


def test_company_saves_only_its_fields(client):
    before = profile(client)
    body = saved(client.post("/hx/setup/company", data={"name": "  Horch & Co <GmbH> ", "address": "Weg 1", "show_on_pdf": "on"}))
    assert 'value="Horch &amp; Co &lt;GmbH&gt;"' in body
    after = profile(client)
    assert (after["name"], after["address"], after["show_on_pdf"]) == ("Horch & Co <GmbH>", "Weg 1", True)
    # nothing of the other pages changed
    for key in ("specification_preamble", "smtp_port", "time_tracking_rounding_minutes", "documentation_include_manuals"):
        assert after[key] == before[key]


def test_unchecked_boxes_mean_off(client):
    saved(client.post("/hx/setup/documentation", data={"documentation_include_circuit_list": "on"}))
    p = profile(client)
    assert p["documentation_include_circuit_list"] is True
    assert p["documentation_include_function_checklist"] is False and p["documentation_include_manuals"] is False


def test_specification_and_email(client):
    saved(client.post("/hx/setup/specification", data={"specification_preamble": "## Hallo", "specification_include_structure": "on"}))
    saved(client.post("/hx/setup/email", data={"smtp_enabled": "on", "smtp_host": "mail.x", "smtp_port": "465",
                                               "smtp_encryption": "ssl", "smtp_password": " geheim "}))
    p = profile(client)
    assert p["specification_preamble"] == "## Hallo" and p["specification_include_preamble"] is False
    assert (p["smtp_host"], p["smtp_port"], p["smtp_encryption"], p["smtp_password"]) == ("mail.x", 465, "ssl", " geheim ")


def test_validation(client):
    assert client.post("/hx/setup/time-tracking", data={"time_tracking_rounding_minutes": "7"}).status_code == 400
    assert client.post("/hx/setup/backup", data={"backup_interval_hours": "0", "backup_retention_count": "5"}).status_code == 400
    assert client.post("/hx/setup/email", data={"smtp_port": "abc", "smtp_encryption": "ssl"}).status_code == 400
    assert client.post("/hx/setup/email", data={"smtp_port": "25", "smtp_encryption": "rot13"}).status_code == 400


def test_time_tracking_switch(client):
    saved(client.post("/hx/setup/time-tracking", data={"time_tracking_rounding_minutes": "30"}))
    p = profile(client)
    assert (p["time_tracking_enabled"], p["time_tracking_rounding_minutes"]) == (False, 30)


def test_backup_now_and_files(client, tmp_path):
    target = tmp_path / "backups"
    target.mkdir()
    saved(client.post("/hx/setup/backup", data={"backup_interval_hours": "24", "backup_retention_count": "3",
                                                "backup_local_enabled": "on", "backup_local_path": str(target)}))
    r = client.post("/hx/setup/backup/run")
    assert json.loads(r.headers["HX-Trigger"])["show-toast"]["level"] == "success"
    assert "Letzte Sicherung:" in r.text
    files = client.get("/hx/setup/backup/files").text
    assert "knxpilot_backup_" in files and "NAS" in files and "Herunterladen" in files


def test_backup_without_destination_reports_error(client):
    r = client.post("/hx/setup/backup/run")
    toast = json.loads(r.headers["HX-Trigger"])["show-toast"]
    assert toast["level"] == "error" and "Kein Ziel" in toast["message"]
    assert "Keine Sicherungen gefunden" in client.get("/hx/setup/backup/files").text
