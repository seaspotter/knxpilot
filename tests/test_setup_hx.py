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


# ---------- list editors ----------
def lists_changed(response):
    assert response.status_code == 200, response.text
    assert json.loads(response.headers["HX-Trigger"])["setup-lists-changed"] is True
    return response.text


def test_category_inline_rename(client):
    cat = ok(client.get("/api/categories"))[1]
    form = client.get(f"/hx/setup/categories/{cat['id']}/edit").text
    assert f'hx-put="/hx/setup/categories/{cat["id"]}"' in form and f'value="{cat["name"]}"' in form
    body = lists_changed(client.put(f"/hx/setup/categories/{cat['id']}", data={"name": "Licht & Co"}))
    assert "Licht &amp; Co" in body
    other = ok(client.get("/api/categories"))[2]["name"]
    assert client.put(f"/hx/setup/categories/{cat['id']}", data={"name": other}).status_code == 400   # duplicate
    assert client.put(f"/hx/setup/categories/{cat['id']}", data={"name": " "}).status_code == 400


def test_function_type_create_edit_delete(client):
    cat = ok(client.get("/api/categories"))[0]["id"]
    body = lists_changed(client.post("/hx/setup/function-types", data={
        "category_id": cat, "name": "Test <Typ>", "block_size": "4", "channel_type": "Schalten", "channels_needed": "2",
        "suffix": ["Schalten", "", "Status"], "dpt": ["DPST-1-1", "x", "DPST-1-11"]}))
    assert "Test &lt;Typ&gt;" in body and "Kanal: Schalten ×2" in body
    pt = next(p for p in ok(client.get("/api/point-types")) if p["name"] == "Test <Typ>")
    assert [s["suffix"] for s in pt["suffixes"]] == ["Schalten", "Status"]   # empty row dropped
    edit = client.get(f"/hx/setup/function-types/{pt['id']}/edit").text
    assert "Funktionstyp bearbeiten" in edit and edit.count('name="suffix"') == 2
    lists_changed(client.put(f"/hx/setup/function-types/{pt['id']}", data={
        "category_id": cat, "name": "Umbenannt", "suffix": ["Ein"], "dpt": ["DPST-1-1"]}))
    pt = next(p for p in ok(client.get("/api/point-types")) if p["id"] == pt["id"])
    assert (pt["name"], pt["block_size"], pt["channels_needed"]) == ("Umbenannt", 5, 1)   # defaults
    assert client.post("/hx/setup/function-types", data={"category_id": cat, "name": "Ohne DP"}).status_code == 400
    assert client.post("/hx/setup/function-types", data={"name": "Ohne Kategorie", "suffix": ["x"], "dpt": ["y"]}).status_code == 400
    lists_changed(client.delete(f"/hx/setup/function-types/{pt['id']}"))
    assert all(p["id"] != pt["id"] for p in ok(client.get("/api/point-types")))


def test_function_types_clear_skips_used_ones(client):
    from conftest import seed_musterhaus
    seed_musterhaus(client, wire=False)
    r = client.delete("/hx/setup/function-types")
    toast = json.loads(r.headers["HX-Trigger"])["show-toast"]["message"]
    assert "in Verwendung übersprungen" in toast
    assert ok(client.get("/api/point-types"))   # the used ones remain


def test_central_template_scope_fields(client):
    cat = ok(client.get("/api/categories"))[0]["id"]
    lists_changed(client.post("/hx/setup/central-templates", data={
        "category_id": cat, "scope": "floor", "name": "Z", "skip_outdoor_floors": "on",
        "block_size": "9", "trigger_count": "3", "suffix": ["Aus"], "dpt": ["DPST-1-1"]}))
    ct = next(c for c in ok(client.get("/api/central-templates")) if c["name"] == "Z")
    # floor scope: skip-outdoor kept, room_multi-only fields ignored
    assert (ct["skip_outdoor_floors"], ct["block_size"], ct["trigger_count"]) == (True, None, None)
    edit = client.get(f"/hx/setup/central-templates/{ct['id']}/edit").text
    assert 'data-scope="floor"' in edit and "Vorlage bearbeiten" in edit
    lists_changed(client.put(f"/hx/setup/central-templates/{ct['id']}", data={
        "category_id": cat, "scope": "room_multi", "name": "Z", "skip_outdoor_floors": "on",
        "block_size": "9", "trigger_count": "3", "suffix": ["Aus"], "dpt": ["DPST-1-1"]}))
    ct2 = next(c for c in ok(client.get("/api/central-templates")) if c["id"] == ct["id"])
    assert (ct2["skip_outdoor_floors"], ct2["block_size"], ct2["trigger_count"], ct2["order_idx"]) == (False, 9, 3, ct["order_idx"])
    assert client.post("/hx/setup/central-templates", data={"category_id": cat, "scope": "galaxy", "suffix": ["a"], "dpt": ["b"]}).status_code == 400
    r = client.delete("/hx/setup/central-templates")
    assert "gelöscht" in json.loads(r.headers["HX-Trigger"])["show-toast"]["message"] and ok(client.get("/api/central-templates")) == []


def test_suffix_row(client):
    row = client.get("/hx/setup/suffix-row?placeholder=Suffix%20z.B.%20Ein").text
    assert 'name="suffix"' in row and 'placeholder="Suffix z.B. Ein"' in row
