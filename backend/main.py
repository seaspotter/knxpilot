"""
KNXpilot
--------------------------------
Modeled directly on real exported ETS6 projects.

Copyright (C) 2026 the project author(s).
Licensed under the GNU Affero General Public License v3.0 or later.
See the LICENSE file in the repository root for the full text.

Addressing model (3-level):
    Main Group   = Function category  (Allgemein, Beleuchtung, Steckdosen, Heizung, Rollo, Tore, ...)
    Middle Group = Floor  (or "Zentralfunktionen" for central/collective addresses; or a themed
                   block name for the Allgemein category, e.g. "Datum/Uhrzeit", "Klima")
    Sub Group    = One address block per physical point ("{Room} {Label} {Suffix}"),
                   padded with reserved "res" addresses up to a fixed block size.

CSV export format (verified against real ETS6 exports):
    Tab-separated, every field quoted, columns:
    Main / Middle / Sub / Address / Central / Unfiltered / Description / DatapointType / Security
    DPTs are written as "DPST-x-y". Security is always "Auto".

This file just wires everything together - see backend/routers/ for the
actual endpoints, grouped by tab (setup, geraete, projects, abgangsliste,
geraeteplanung, verteiler, klaerungsliste, pflichtenheft, system), backend/db.py for the
schema/migrations/seed data, backend/ga_logic.py for GA-tree generation, and
backend/pdf_design.py for the shared PDF look-and-feel. The frontend (plain
HTML/CSS/JS, no build step) lives in ../frontend/, mounted below.

Run with: uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .backup import run_backup_now
from .db import get_db, init_db
from .routers import setup, geraete, projects, abgangsliste, geraeteplanung, klaerungsliste, pflichtenheft, system, verteiler

logger = logging.getLogger("knxpilot.backup")

# How often the background loop wakes up to check whether a backup is due -
# just the polling granularity, not the backup cadence itself (that's
# company_profile.backup_interval_hours, set in Setup -> Backup).
BACKUP_CHECK_INTERVAL_SECONDS = 900


def _maybe_run_scheduled_backup():
    """Runs inside a worker thread (via asyncio.to_thread below) - opens
    its own db connection rather than being handed one, since sqlite3
    connections can't cross threads with the default check_same_thread."""
    with get_db() as db:
        cp = dict(db.execute("SELECT * FROM company_profile WHERE id=1").fetchone())
        if not cp["backup_enabled"]:
            return
        due = True
        if cp["backup_last_run_at"]:
            last = datetime.fromisoformat(cp["backup_last_run_at"])
            due = (datetime.now(timezone.utc) - last) >= timedelta(hours=cp["backup_interval_hours"])
        if due:
            run_backup_now(db)


async def _backup_scheduler_loop():
    while True:
        await asyncio.sleep(BACKUP_CHECK_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(_maybe_run_scheduled_backup)
        except Exception:
            logger.exception("Backup scheduler iteration failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_backup_scheduler_loop())
    yield
    task.cancel()


app = FastAPI(title="KNXpilot", lifespan=lifespan)

init_db()

app.include_router(setup.router)
app.include_router(geraete.router)
app.include_router(projects.router)
app.include_router(abgangsliste.router)
app.include_router(geraeteplanung.router)
app.include_router(verteiler.router)
app.include_router(klaerungsliste.router)
app.include_router(pflichtenheft.router)
app.include_router(system.router)

class NoCacheStaticFiles(StaticFiles):
    """Serves frontend/ with Cache-Control: no-cache instead of Starlette's
    default (browser-cacheable with no revalidation hint). The self-update
    flow (git pull + restart, see routers/system.py) changes these files
    on disk without changing their URLs, so a plain browser cache would
    keep serving pre-update HTML/CSS/JS after a restart until the user
    happens to hard-refresh. no-cache still lets the browser keep a local
    copy - it just forces a conditional GET (via the ETag/Last-Modified
    headers FileResponse already sends) before using it, so an unchanged
    file is a cheap 304 and a changed one is picked up immediately."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/", NoCacheStaticFiles(directory=Path(__file__).parent.parent / "frontend", html=True), name="static")
