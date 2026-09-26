"""
Device manuals: Geräte Katalog -> Handbücher lets the user curate a
manufacturer PDF URL per device type (actor_types.manual_url); this router
fetches that URL for whichever devices are actually used in a project (via
geraeteplanung.device_summary()) and stores the result in this project's
own Handbücher tab (db.py's project_manuals table) - kept separate from
project_files.py's Dateien, which is only ever what the user themselves
uploaded.

This is a plain http(s) GET of a URL the user themselves typed into their
own catalog - not a search/scrape - and only ever runs when the user
clicks the button, never automatically (matches the same "manual, confirm
first" choice made for routers/email.py's send action).
"""
import http.client
import urllib.error
import urllib.request
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..db import get_db
from .geraeteplanung import device_summary
from ..utils import content_disposition

router = APIRouter(tags=["manuals"])

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB - same cap as project_files.py's uploads


def _fetch_manual_bytes(url):
    """Downloads a manual from a manufacturer-provided URL, capped at
    MAX_FILE_SIZE - only http(s) schemes are allowed (the URL is admin-
    curated in the device catalog, not arbitrary end-user input, but
    rejecting other schemes is a cheap, free guard against e.g. a pasted
    local file:// path). Raises ValueError with a ready-to-show German
    message on any failure, so the caller doesn't need to translate
    exception types itself.

    Only real PDFs are accepted (checked by the file's %PDF magic bytes,
    not the server's claimed Content-Type): a link that's gone stale often
    lands on an HTML page instead, which would otherwise be stored and later
    served from KNXpilot's own origin, and counted as "Vorhanden" in the
    Dokumentation's Handbücher chapter."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Nur http(s)-URLs werden unterstützt.")
    req = urllib.request.Request(url, headers={"User-Agent": "KNXpilot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            expected = resp.headers.get("Content-Length")
            chunks = []
            total = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FILE_SIZE:
                    raise ValueError(f"Datei zu gross (max. {MAX_FILE_SIZE // (1024 * 1024)} MB).")
                chunks.append(chunk)
            # read(n) just returns b"" when the connection drops early - it
            # doesn't raise - so a truncated body has to be caught here.
            if expected and expected.isdigit() and total < int(expected):
                raise ValueError(f"Download unvollständig ({total} von {expected} Bytes).")
    except urllib.error.HTTPError as e:
        raise ValueError(f"Server antwortete mit Fehler {e.code}.") from e
    except urllib.error.URLError as e:
        raise ValueError(f"Nicht erreichbar: {e.reason}") from e
    except (OSError, http.client.HTTPException) as e:
        # Timeout or dropped connection mid-download - URLError only covers
        # failures while connecting.
        raise ValueError(f"Download abgebrochen: {e or type(e).__name__}") from e
    data = b"".join(chunks)
    if not data.lstrip()[:5].startswith(b"%PDF"):
        raise ValueError("Kein PDF - der Link führt vermutlich auf eine Webseite statt direkt auf das Handbuch.")
    return data, "application/pdf"


@router.get("/api/projects/{project_id}/manuals")
def list_project_manuals(project_id: int):
    """Every device used in the project that has a curated manual_url in
    the catalog, annotated with whether it's already been fetched into
    this project's own Handbücher tab."""
    with get_db() as db:
        if not db.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone():
            raise HTTPException(404, "Project not found")
        fetched = {
            r["device_type_id"]: r["id"]
            for r in db.execute(
                "SELECT id, device_type_id FROM project_manuals WHERE project_id=?", (project_id,)
            ).fetchall()
        }

    result = []
    for d in device_summary(project_id):
        if not d["manual_url"]:
            continue
        result.append({
            "device_type_id": d["device_type_id"],
            "device_name": d["device_name"],
            "description": d["description"],
            "manual_url": d["manual_url"],
            "file_id": fetched.get(d["device_type_id"]),
        })
    return result


@router.get("/api/project-manuals/{file_id}/view")
def view_project_manual(file_id: int):
    """Inline (not attachment) response so clicking opens the PDF directly
    in a new browser tab via the native PDF viewer, instead of forcing a
    download."""
    with get_db() as db:
        row = db.execute(
            "SELECT device_name, content_type, data FROM project_manuals WHERE id=?", (file_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Manual not found")
        # Always served as a PDF with nosniff - never with a stored,
        # remote-claimed type (see _fetch_manual_bytes), so nothing fetched
        # can ever render as HTML on KNXpilot's own origin.
        return Response(
            content=row["data"],
            media_type="application/pdf",
            headers={
                "Content-Disposition": content_disposition(f"{row['device_name']} Handbuch.pdf", "inline"),
                "X-Content-Type-Options": "nosniff",
            },
        )


@router.post("/api/projects/{project_id}/fetch-manual/{device_type_id}")
def fetch_project_manual(project_id: int, device_type_id: int):
    """Fetches one device's curated manual URL and saves it into this
    project's Handbücher tab - only ever runs on this explicit click,
    never automatically. Re-clicking after it's already been fetched is a
    no-op (matched by the UNIQUE(project_id, device_type_id) constraint)
    rather than a duplicate download."""
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        device_type = db.execute("SELECT * FROM actor_types WHERE id=?", (device_type_id,)).fetchone()
        if not device_type or not device_type["manual_url"]:
            raise HTTPException(404, "Kein Handbuch-Link für dieses Gerät hinterlegt.")

        existing = db.execute(
            "SELECT id FROM project_manuals WHERE project_id=? AND device_type_id=?",
            (project_id, device_type_id),
        ).fetchone()
        if existing:
            return {"ok": True, "already_downloaded": True, "file_id": existing["id"]}

        try:
            data, content_type = _fetch_manual_bytes(device_type["manual_url"])
        except ValueError as e:
            raise HTTPException(502, str(e))

        device_name = " ".join(p for p in (device_type["manufacturer"], device_type["model"]) if p) or "Gerät"
        cur = db.execute(
            "INSERT INTO project_manuals (project_id, device_type_id, device_name, content_type, size_bytes, data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, device_type_id, device_name, content_type, len(data), data),
        )
        return {"ok": True, "already_downloaded": False, "file_id": cur.lastrowid}


@router.post("/api/projects/{project_id}/fetch-manuals")
def fetch_all_project_manuals(project_id: int):
    """Bulk variant of fetch_project_manual() above - fetches every
    not-yet-downloaded manual for the project in one request, tolerating
    individual failures (a broken link for one device shouldn't block the
    rest)."""
    manuals = list_project_manuals(project_id)
    fetched, already, failed = [], [], []
    for m in manuals:
        if m["file_id"]:
            already.append(m["device_name"])
            continue
        try:
            fetch_project_manual(project_id, m["device_type_id"])
            fetched.append(m["device_name"])
        except HTTPException as e:
            failed.append({"device_name": m["device_name"], "error": e.detail})
    return {"fetched": fetched, "already_downloaded": already, "failed": failed}


@router.delete("/api/project-manuals/{file_id}")
def delete_project_manual(file_id: int):
    with get_db() as db:
        db.execute("DELETE FROM project_manuals WHERE id=?", (file_id,))
    return {"ok": True}
