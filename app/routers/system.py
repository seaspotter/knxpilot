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

from fastapi import APIRouter, BackgroundTasks

router = APIRouter(tags=["system"])

REPO_DIR = "/app"


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
                    "Updated, but requirements.txt or the Dockerfile changed - a full rebuild is needed. "
                    "Run on the server: docker compose up -d --build"
                ),
                "restarting": False,
            }

        background_tasks.add_task(_restart_process)
        return {"ok": True, "message": "Updated. Restarting now...", "restarting": True}
    except subprocess.TimeoutExpired:
        return {"ok": False, "message": "git pull timed out", "restarting": False}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "message": e.stderr or str(e), "restarting": False}
