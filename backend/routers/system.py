"""
Self-update via git (see docker-compose.yml: the whole repo is mounted
into the container at /app, so a `git pull` here updates the live code -
a process restart then picks it up, no image rebuild needed for pure
code changes. If requirements.txt or the Dockerfile changed, we deliberately
do NOT auto-restart, since the new dependencies wouldn't be installed yet.
"""
import os
import subprocess
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response

from ..backup import (
    BACKUP_FILENAME_RE, download_nextcloud_backup, list_local_backups, list_nextcloud_backups,
    restore_database, run_backup_now,
)
from ..db import get_db

router = APIRouter(tags=["system"])

REPO_DIR = "/app"

# Self-relative (not REPO_DIR) so this works in local dev too, not just the
# container - unlike the git-based endpoints below, which only make sense
# against the bind-mounted repo checkout.
CHANGELOG_PATH = Path(__file__).parent.parent.parent / "CHANGELOG.md"
MANUAL_PATH = Path(__file__).parent.parent.parent / "MANUAL.md"


@router.get("/api/system/changelog")
def get_changelog():
    try:
        return {"markdown": CHANGELOG_PATH.read_text(encoding="utf-8")}
    except FileNotFoundError:
        return {"markdown": ""}


@router.get("/api/system/manual")
def get_manual():
    try:
        return {"markdown": MANUAL_PATH.read_text(encoding="utf-8")}
    except FileNotFoundError:
        return {"markdown": ""}


@router.get("/api/system/version")
def get_version():
    """Local-only (no network fetch), so this is cheap enough to call on every
    page load for a persistent header badge - unlike /system/status below,
    which does a git fetch and is only meant to run on an explicit click."""
    try:
        result = subprocess.run(
            ["git", "-C", REPO_DIR, "describe", "--tags", "--always", "--dirty"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return {"version": result.stdout.strip()}
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {"version": None}


@router.get("/api/system/status")
def system_status():
    try:
        subprocess.run(["git", "-C", REPO_DIR, "fetch"], capture_output=True, text=True, timeout=30, check=True)
        current = subprocess.run(
            ["git", "-C", REPO_DIR, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        try:
            latest = subprocess.run(
                ["git", "-C", REPO_DIR, "rev-parse", "--short", "@{u}"], capture_output=True, text=True, check=True
            ).stdout.strip()
        except subprocess.CalledProcessError:
            return {
                "current": current, "latest": None, "update_available": False,
                "error": "No upstream branch configured. Run once: git branch --set-upstream-to=origin/main main",
            }
        return {"current": current, "latest": latest, "update_available": current != latest, "error": None}
    except FileNotFoundError:
        return {"current": None, "latest": None, "update_available": False, "error": "git is not installed in this container"}
    except subprocess.CalledProcessError as e:
        return {"current": None, "latest": None, "update_available": False, "error": (e.stderr or str(e))[:500]}
    except subprocess.TimeoutExpired:
        return {"current": None, "latest": None, "update_available": False, "error": "git fetch timed out"}


def _restart_process():
    time.sleep(1)  # let the HTTP response actually reach the browser first
    os._exit(0)  # docker-compose's `restart: unless-stopped` brings it back with the new code


@router.post("/api/system/update")
def system_update(background_tasks: BackgroundTasks):
    try:
        before = subprocess.run(
            ["git", "-C", REPO_DIR, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        result = subprocess.run(["git", "-C", REPO_DIR, "pull", "--ff-only"], capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return {"ok": False, "message": result.stderr or result.stdout, "restarting": False}

        after = subprocess.run(
            ["git", "-C", REPO_DIR, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        if before == after:
            return {"ok": True, "message": "Already up to date.", "restarting": False}

        changed = subprocess.run(
            ["git", "-C", REPO_DIR, "diff", "--name-only", before, after], capture_output=True, text=True, check=True
        ).stdout
        if "requirements.txt" in changed or "Dockerfile" in changed:
            return {
                "ok": True,
                "message": (
                    "Updated, but requirements.txt or the Dockerfile changed - a new image is needed. "
                    "Run on the server: docker compose pull && docker compose up -d"
                ),
                "restarting": False,
            }

        background_tasks.add_task(_restart_process)
        return {"ok": True, "message": "Updated. Restarting now...", "restarting": True}
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "git pull timed out", "restarting": False}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "message": e.stderr or str(e), "restarting": False}


@router.post("/api/system/backup")
def trigger_backup():
    """Manual "Jetzt sichern" trigger (Setup -> Backup) - runs the same
    logic as the automatic scheduler in main.py, just on demand. Always
    returns 200 with a result payload rather than raising, even on
    per-destination failure, since a partial failure (e.g. local ok,
    Nextcloud unreachable) is still useful status to show, not a hard
    error the caller needs to catch."""
    with get_db() as db:
        return run_backup_now(db)


def _backup_settings():
    with get_db() as db:
        return dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())


@router.get("/api/system/backups")
def list_backups():
    """Existing backups in every enabled destination, for Setup ->
    Backup's "Vorhandene Sicherungen" list. Nextcloud listing failures
    (e.g. wrong URL/credentials) are reported back as nextcloud_error
    rather than raising, so a broken Nextcloud connection doesn't also
    hide an otherwise-working local listing."""
    cp = _backup_settings()
    local = list_local_backups(cp["backup_local_path"]) if cp["backup_local_enabled"] else []
    nextcloud, nextcloud_error = [], None
    if cp["backup_nextcloud_enabled"]:
        try:
            nextcloud = list_nextcloud_backups(
                cp["backup_nextcloud_url"], cp["backup_nextcloud_username"], cp["backup_nextcloud_password"]
            )
        except Exception as e:
            nextcloud_error = str(e)
    return {"local": local, "nextcloud": nextcloud, "nextcloud_error": nextcloud_error}


@router.get("/api/system/backups/{filename}/download")
def download_backup(filename: str):
    if not BACKUP_FILENAME_RE.match(filename):
        raise HTTPException(400, "Invalid filename")
    cp = _backup_settings()
    if not cp["backup_local_enabled"]:
        raise HTTPException(404, "Local backup destination not enabled")
    file_path = Path(cp["backup_local_path"]) / filename
    if not file_path.is_file():
        raise HTTPException(404, "Backup not found")
    return FileResponse(file_path, filename=filename, media_type="application/octet-stream")


@router.get("/api/system/backups/nextcloud/{filename}/download")
def download_backup_nextcloud(filename: str):
    if not BACKUP_FILENAME_RE.match(filename):
        raise HTTPException(400, "Invalid filename")
    cp = _backup_settings()
    if not cp["backup_nextcloud_enabled"]:
        raise HTTPException(404, "Nextcloud destination not enabled")
    try:
        data = download_nextcloud_backup(
            cp["backup_nextcloud_url"], cp["backup_nextcloud_username"], cp["backup_nextcloud_password"], filename
        )
    except Exception as e:
        raise HTTPException(502, f"Nextcloud-Download fehlgeschlagen: {e}")
    return Response(
        content=data, media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _restore_and_restart(data, background_tasks):
    try:
        restore_database(data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    background_tasks.add_task(_restart_process)
    return {"ok": True, "message": "Wiederhergestellt. Startet neu...", "restarting": True}


@router.post("/api/system/restore-local/{filename}")
def restore_from_local(filename: str, background_tasks: BackgroundTasks):
    """Restores directly from a file already sitting in the local backup
    folder - no upload round-trip needed since the backend can already
    read it."""
    if not BACKUP_FILENAME_RE.match(filename):
        raise HTTPException(400, "Invalid filename")
    cp = _backup_settings()
    if not cp["backup_local_enabled"]:
        raise HTTPException(404, "Local backup destination not enabled")
    file_path = Path(cp["backup_local_path"]) / filename
    if not file_path.is_file():
        raise HTTPException(404, "Backup not found")
    return _restore_and_restart(file_path.read_bytes(), background_tasks)


@router.post("/api/system/restore-nextcloud/{filename}")
def restore_from_nextcloud(filename: str, background_tasks: BackgroundTasks):
    """Restores from a file already sitting in the Nextcloud backup
    folder - downloads it via WebDAV first, then goes through the same
    validate+safety-snapshot+replace path as any other restore."""
    if not BACKUP_FILENAME_RE.match(filename):
        raise HTTPException(400, "Invalid filename")
    cp = _backup_settings()
    if not cp["backup_nextcloud_enabled"]:
        raise HTTPException(404, "Nextcloud destination not enabled")
    try:
        data = download_nextcloud_backup(
            cp["backup_nextcloud_url"], cp["backup_nextcloud_username"], cp["backup_nextcloud_password"], filename
        )
    except Exception as e:
        raise HTTPException(502, f"Nextcloud-Download fehlgeschlagen: {e}")
    return _restore_and_restart(data, background_tasks)


@router.post("/api/system/restore-upload")
async def restore_from_upload(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Restores from an uploaded .db file - works for a Nextcloud backup
    (download it from Nextcloud's web UI first) or any other copy of a
    KNXpilot database, not just ones this install itself produced."""
    data = await file.read()
    return _restore_and_restart(data, background_tasks)
