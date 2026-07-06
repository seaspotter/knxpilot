"""
KNX Projekttool
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

This file just wires everything together - see app/routers/ for the actual
endpoints, grouped by tab (setup, geraete, projects, abgangsliste,
geraeteplanung, pflichtenheft, system), app/db.py for the schema/migrations/
seed data, app/ga_logic.py for GA-tree generation, and app/pdf_design.py for
the shared PDF look-and-feel.

Run with: uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .db import init_db
from .routers import setup, geraete, projects, abgangsliste, geraeteplanung, pflichtenheft, system

app = FastAPI(title="KNX Projekttool")

init_db()

app.include_router(setup.router)
app.include_router(geraete.router)
app.include_router(projects.router)
app.include_router(abgangsliste.router)
app.include_router(geraeteplanung.router)
app.include_router(pflichtenheft.router)
app.include_router(system.router)

app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
