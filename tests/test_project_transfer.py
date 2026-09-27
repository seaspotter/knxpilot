"""Per-project JSON: the backup (export-json -> import-json) restores the
complete project with every reference remapped to the new ids; "Duplizieren"
copies the planning data only."""
import sqlite3

from conftest import ok, seed_musterhaus

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


def rich_project(client, db_path):
    pid = seed_musterhaus(client)
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    eg = tree["floors"][0]
    flur = next(r for r in eg["rooms"] if r["name"] == "Flur")
    point = eg["rooms"][0]["points"][0]
    at = {a["model"]: a["id"] for a in ok(client.get("/api/actor-types"))}

    line = ok(client.post(f"/api/projects/{pid}/lines", json={"area": 1, "line": 1, "name": "Haus"}))["id"]
    ok(client.put(f"/api/floors/{eg['id']}/line", json={"line_id": line}))
    ok(client.post(f"/api/floors/{eg['id']}/devices", json={"device_type_id": at["SCN-IP000.03"], "note": "Router"}))
    ok(client.put(f"/api/projects/{pid}/device-order-flags/{at['SCN-BWM63.02']}", json={"not_ordering": True}))
    actor = ok(client.get(f"/api/projects/{pid}/actor-instances"))[0]
    vid = ok(client.post(f"/api/projects/{pid}/distribution-boards", json={"room_id": flur["id"], "name": "UV EG"}))["id"]
    ok(client.post(f"/api/distribution-boards/{vid}/items", json={"row_idx": 0, "item_type": "rcd", "label": "RCD 40A"}))
    ok(client.post(f"/api/distribution-boards/{vid}/items", json={"row_idx": 1, "item_type": "device", "actor_instance_id": actor["id"]}))
    ok(client.post(f"/api/projects/{pid}/clarifications", json={"text": "Spots dimmbar?", "room_id": eg["rooms"][0]["id"], "room_point_id": point["id"]}))
    central_key = ok(client.get(f"/api/projects/{pid}/central-functions-checklist"))[0][1][0]["key"]
    for key in (f"room_point:{point['id']}", central_key, "uebergabe:funktionen_geprueft"):
        ok(client.put(f"/api/projects/{pid}/checklist-status/{key}", json={"status": "ok", "note": "n"}))
    ok(client.put(f"/api/projects/{pid}/signatures/fc_systemintegrator", json={"image": PNG}))
    client.get(f"/api/projects/{pid}/export.csv")  # sets the ETS export snapshot
    ok(client.post(f"/api/projects/{pid}/files", files={"file": ("Plan Süd.pdf", b"%PDF-1.4 plan", "application/pdf")}))
    with sqlite3.connect(db_path) as db:  # a fetched manual (fetching itself needs the internet)
        db.execute("INSERT INTO project_manuals (project_id, device_type_id, device_name, content_type, size_bytes, data) "
                   "VALUES (?, ?, 'MDT AKS-2016.03', 'application/pdf', 4, ?)", (pid, at["AKS-2016.03"], b"%PDF"))
    return pid


def snapshot(client, db_path, pid):
    """Everything project-related, with ids replaced by names/positions so two
    projects can be compared."""
    tree = ok(client.get(f"/api/projects/{pid}/tree"))
    point_pos = {p["id"]: (fi, ri, pi) for fi, f in enumerate(tree["floors"]) for ri, r in enumerate(f["rooms"])
                 for pi, p in enumerate(r["points"])}
    actors = ok(client.get(f"/api/projects/{pid}/actor-instances"))
    actor_pos = {a["id"]: i for i, a in enumerate(actors)}
    circuits = ok(client.get(f"/api/projects/{pid}/circuits"))
    status = ok(client.get(f"/api/projects/{pid}/checklist-status"))
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        q = lambda sql: [dict(r) for r in db.execute(sql, (pid,))]
        return {
            "tree": [(f["name"], f["line_id"] is not None, [(r["name"], len(r["points"])) for r in f["rooms"]]) for f in tree["floors"]],
            "actors": [(a["actor_type_id"], a["physical_address"], a["location_label"]) for a in actors],
            "circuits": sorted((point_pos[c["room_point_id"]], c["channel_seq"], actor_pos[c["assignment"]["actor_instance_id"]],
                                c["assignment"]["channel_letter"]) for c in circuits if c["assignment"]),
            "summary": [(d["device_name"], d["total"], d["not_ordering"]) for d in ok(client.get(f"/api/projects/{pid}/device-summary"))],
            "distribution_boards": [(b["name"], b["room_name"], [[(i["item_type"], i["label"]) for i in row] for row in b["rows"]])
                          for b in ok(client.get(f"/api/projects/{pid}/distribution-boards"))],
            "clarifications": [(c["text"], c["room_point_id"] is not None) for c in q("SELECT * FROM clarifications WHERE project_id=?")],
            "checklist": sorted((k.split(":")[0], v["status"], v["note"]) for k, v in status.items()),
            "checklist_point_ok": [point_pos[int(k.split(":")[1])] for k in status if k.startswith("room_point:")],
            "signatures": [r["role"] for r in q("SELECT role FROM project_signatures WHERE project_id=?")],
            "snapshot": len(q("SELECT 1 FROM ga_export_snapshots WHERE project_id=?")),
            "files": [(r["filename"], r["data"]) for r in q("SELECT filename, data FROM project_files WHERE project_id=?")],
            "manuals": [r["device_name"] for r in q("SELECT device_name FROM project_manuals WHERE project_id=?")],
        }


def test_backup_restores_everything(client, db_path):
    pid = rich_project(client, db_path)
    before = snapshot(client, db_path, pid)
    payload = client.get(f"/api/projects/{pid}/export-json").json()
    assert payload["format"] == "knx-ga-project-v1.2" and payload["mode"] == "backup"

    restored = ok(client.post("/api/projects/import-json", json=payload))
    assert restored["name"] == "Musterhaus (imported)" and restored["skipped"] == []
    after = snapshot(client, db_path, restored["id"])
    assert after == before
    # sanity: the comparison really covered the rich parts
    assert before["circuits"] and before["distribution_boards"][0][1] == "Flur" and before["files"][0][1] == b"%PDF-1.4 plan"
    assert len(before["checklist"]) == 3 and before["signatures"] == ["fc_systemintegrator"] and before["manuals"]


def test_duplicate_copies_planning_only(client, db_path):
    pid = rich_project(client, db_path)
    before = snapshot(client, db_path, pid)
    copy = ok(client.post(f"/api/projects/{pid}/duplicate"))
    after = snapshot(client, db_path, copy["id"])
    for key in ("tree", "actors", "circuits", "summary", "distribution_boards"):
        assert after[key] == before[key], key
    assert after["clarifications"] == [] and after["checklist"] == [] and after["signatures"] == []
    assert after["snapshot"] == 0 and after["files"] == [] and after["manuals"] == []


def test_old_backup_format_still_imports(client):
    old = {"format": "knx-ga-project-v1.1", "project_name": "Alt", "floors": [
        {"name": "EG", "rooms": [{"name": "Bad", "points": [
            {"point_type_name": "Heizkreis", "category_name": "Heizung", "label": "", "has_bwm": False}]}]}],
        "specials": []}
    result = ok(client.post("/api/projects/import-json", json=old))
    tree = ok(client.get(f"/api/projects/{result['id']}/tree"))
    assert [(f["name"], [r["name"] for r in f["rooms"]]) for f in tree["floors"]] == [("EG", ["Bad"])]


def test_unknown_device_is_reported_not_guessed(client, db_path):
    pid = rich_project(client, db_path)
    payload = client.get(f"/api/projects/{pid}/export-json").json()
    payload["actors"][0]["model"] = "GIBT-ES-NICHT"
    result = ok(client.post("/api/projects/import-json", json=payload))
    assert any("GIBT-ES-NICHT" in s for s in result["skipped"])
