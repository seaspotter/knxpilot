"""
KNX Group Address Generator v2
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

Run with: uvicorn app.main:app --host 0.0.0.0 --port 8000
"""
import csv
import io
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DB_PATH = Path(__file__).parent / "data" / "knx_ga.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="KNX GA Generator")


def join_parts(*parts):
    """Join name fragments with a single space, skipping empty ones (avoids double spaces)."""
    return " ".join(p for p in parts if p)


def channel_letters(n):
    """Spreadsheet-style channel labels: A, B, ..., Z, AA, AB, ... for n channels."""
    result = []
    for i in range(1, n + 1):
        label = ""
        x = i
        while x > 0:
            x, rem = divmod(x - 1, 26)
            label = chr(65 + rem) + label
        result.append(label)
    return result


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Schema + seed data
# --------------------------------------------------------------------------
def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                order_idx INTEGER NOT NULL,
                is_allgemein INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS point_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                suffixes_json TEXT NOT NULL,   -- [{"suffix": "Schalten", "dpt": "DPST-1-1"}, ...]
                block_size INTEGER NOT NULL DEFAULT 5,
                channel_type TEXT NOT NULL DEFAULT '',   -- e.g. 'Schalten','Dimmen','Rollo','Heizung','Tor'
                channels_needed INTEGER NOT NULL DEFAULT 1  -- physical actuator channels this point needs
            );

            -- Auto-generated central / thematic blocks per category.
            -- scope='building'   -> one block, name = template name (Allgemein categories use this
            --                        to create their own dedicated Middle Group, e.g. "Klima")
            -- scope='floor'      -> one block per floor, name = "Zentral {floor}"
            -- scope='room_multi' -> one block PER ROOM, only for rooms that have at least
            --                       `trigger_count` points in this category (e.g. a room with
            --                       2+ blinds gets its own "{Room} Zentral Auf/Ab/Stop/Position").
            --                       `block_size` optionally pads with "res" like a Point Type does.
            -- All non-Allgemein scopes land inside one "Zentralfunktionen" Middle Group.
            CREATE TABLE IF NOT EXISTS central_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                scope TEXT NOT NULL,            -- 'building' | 'floor' | 'room_multi'
                suffixes_json TEXT NOT NULL,
                order_idx INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS floors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                order_idx INTEGER NOT NULL,
                is_outdoor INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                floor_id INTEGER NOT NULL REFERENCES floors(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                order_idx INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS room_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                point_type_id INTEGER NOT NULL REFERENCES point_types(id),
                label TEXT NOT NULL DEFAULT '',   -- e.g. "Decke", "Spots", "Nord" - empty for e.g. heating
                order_idx INTEGER NOT NULL,
                has_bwm INTEGER NOT NULL DEFAULT 0   -- adds one extra "BWM" (motion sensor) address
            );

            -- Catch-all for one-off / special addresses that don't fit the generated pattern.
            -- location = 'central' (goes into that category's Zentralfunktionen block)
            --          or a floor_id (appended at the end of that floor's block for the category)
            CREATE TABLE IF NOT EXISTS special_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                category_id INTEGER NOT NULL REFERENCES categories(id),
                location TEXT NOT NULL,       -- 'central' or a floor id as string
                name TEXT NOT NULL,
                suffixes_json TEXT NOT NULL,
                order_idx INTEGER NOT NULL DEFAULT 0
            );

            -- Physical actuator hardware catalog (global, shared across every project).
            CREATE TABLE IF NOT EXISTS actor_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT '',      -- legacy, unused (kept for old-DB compatibility)
                manufacturer TEXT NOT NULL DEFAULT '',
                model TEXT NOT NULL DEFAULT '',     -- e.g. "AKS-2016.03"
                channel_type TEXT NOT NULL,          -- must match a point type's channel_type to be assignable
                channel_count INTEGER NOT NULL
            );

            -- A specific physical device placed in a project (a distribution board slot).
            CREATE TABLE IF NOT EXISTS actor_instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                actor_type_id INTEGER NOT NULL REFERENCES actor_types(id),
                floor_id INTEGER REFERENCES floors(id) ON DELETE SET NULL,
                location_label TEXT NOT NULL DEFAULT '',    -- e.g. "EG Technik Verteilung"
                physical_address TEXT NOT NULL DEFAULT '',  -- e.g. "1.1.2"
                order_idx INTEGER NOT NULL DEFAULT 0
            );

            -- Assigns one physical output ("circuit") of a room_point to one channel of one actor instance.
            -- channel_seq distinguishes multiple channels needed by a single point (see channels_needed).
            CREATE TABLE IF NOT EXISTS channel_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                room_point_id INTEGER NOT NULL REFERENCES room_points(id) ON DELETE CASCADE,
                channel_seq INTEGER NOT NULL DEFAULT 0,
                actor_instance_id INTEGER NOT NULL REFERENCES actor_instances(id) ON DELETE CASCADE,
                channel_letter TEXT NOT NULL,
                UNIQUE(room_point_id, channel_seq),
                UNIQUE(actor_instance_id, channel_letter)
            );
            """
        )

        # Lightweight migrations for DBs created before these columns existed.
        for table, column, ddl in [
            ("floors", "is_outdoor", "ALTER TABLE floors ADD COLUMN is_outdoor INTEGER NOT NULL DEFAULT 0"),
            ("room_points", "has_bwm", "ALTER TABLE room_points ADD COLUMN has_bwm INTEGER NOT NULL DEFAULT 0"),
            ("central_templates", "skip_outdoor_floors",
             "ALTER TABLE central_templates ADD COLUMN skip_outdoor_floors INTEGER NOT NULL DEFAULT 0"),
            ("central_templates", "block_size", "ALTER TABLE central_templates ADD COLUMN block_size INTEGER"),
            ("central_templates", "trigger_count", "ALTER TABLE central_templates ADD COLUMN trigger_count INTEGER"),
            ("point_types", "channel_type", "ALTER TABLE point_types ADD COLUMN channel_type TEXT NOT NULL DEFAULT ''"),
            ("point_types", "channels_needed", "ALTER TABLE point_types ADD COLUMN channels_needed INTEGER NOT NULL DEFAULT 1"),
            ("actor_types", "manufacturer", "ALTER TABLE actor_types ADD COLUMN manufacturer TEXT NOT NULL DEFAULT ''"),
            ("actor_types", "model", "ALTER TABLE actor_types ADD COLUMN model TEXT NOT NULL DEFAULT ''"),
        ]:
            cols = [r["name"] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
            if column not in cols:
                db.execute(ddl)

        # One-time backfill: any actor_types created before manufacturer/model existed had
        # everything in the old "name" column - carry that into "model" so nothing is lost.
        db.execute("UPDATE actor_types SET model = name WHERE model = '' AND name != ''")

        (count,) = db.execute("SELECT COUNT(*) FROM categories").fetchone()
        if count == 0:
            seed_defaults(db)


def seed_defaults(db):
    """Seed categories, point types and central templates from the analysed real projects."""

    def add_category(name, order_idx, is_allgemein=False):
        cur = db.execute(
            "INSERT INTO categories (name, order_idx, is_allgemein) VALUES (?, ?, ?)",
            (name, order_idx, int(is_allgemein)),
        )
        return cur.lastrowid

    def add_point_type(cat_id, name, suffixes, block_size, channel_type="", channels_needed=1):
        db.execute(
            "INSERT INTO point_types (category_id, name, suffixes_json, block_size, channel_type, channels_needed) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (cat_id, name, json.dumps(suffixes), block_size, channel_type, channels_needed),
        )

    def add_central(cat_id, name, scope, suffixes, order_idx=0, skip_outdoor_floors=False,
                     block_size=None, trigger_count=None):
        db.execute(
            "INSERT INTO central_templates "
            "(category_id, name, scope, suffixes_json, order_idx, skip_outdoor_floors, block_size, trigger_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (cat_id, name, scope, json.dumps(suffixes), order_idx, int(skip_outdoor_floors),
             block_size, trigger_count),
        )

    # --- Allgemein (Main 0) ---------------------------------------------
    allgemein = add_category("Allgemein", 0, is_allgemein=True)
    add_central(
        allgemein, "Datum/Uhrzeit", "building",
        [
            {"suffix": "Datum", "dpt": "DPST-11-1"},
            {"suffix": "Uhrzeit", "dpt": "DPST-10-1"},
            {"suffix": "Datum/Uhrzeit", "dpt": "DPST-19-1"},
            {"suffix": "Tag/Nacht", "dpt": "DPST-1-2"},
        ],
        order_idx=0,
    )
    add_central(
        allgemein, "Klima", "building",
        [
            {"suffix": "Aussentemperatur Nord", "dpt": "DPST-9-1"},
            {"suffix": "Aussentemperatur Dach", "dpt": "DPST-9-1"},
            {"suffix": "Windgeschwindigkeit", "dpt": "DPST-9-5"},
            {"suffix": "Regen", "dpt": "DPST-1-1"},
            {"suffix": "Helligkeit Süd", "dpt": "DPST-9-4"},
            {"suffix": "Helligkeit West", "dpt": "DPST-9-4"},
            {"suffix": "Helligkeit Ost", "dpt": "DPST-9-4"},
            {"suffix": "Windalarm", "dpt": "DPST-1-5"},
        ],
        order_idx=1,
    )

    # --- Beleuchtung (Lighting) ------------------------------------------
    beleuchtung = add_category("Beleuchtung", 1)
    add_point_type(
        beleuchtung, "Licht (Schalten)",
        [{"suffix": "Schalten", "dpt": "DPST-1-1"}, {"suffix": "Schalten Status", "dpt": "DPST-1-11"}],
        block_size=5,
        channel_type="Schalten",
    )
    add_point_type(
        beleuchtung, "Licht (Dimmen)",
        [
            {"suffix": "Schalten", "dpt": "DPST-1-1"},
            {"suffix": "Schalten Status", "dpt": "DPST-1-11"},
            {"suffix": "Dimmen", "dpt": "DPST-3-7"},
            {"suffix": "Dimmen Status", "dpt": "DPST-5-1"},
        ],
        block_size=5,
        channel_type="Dimmen",
    )
    add_point_type(
        beleuchtung, "LED (Tunable White)",
        [
            {"suffix": "Schalten", "dpt": "DPST-1-1"},
            {"suffix": "Schalten Status", "dpt": "DPST-1-11"},
            {"suffix": "Helligkeit relativ", "dpt": "DPST-3-7"},
            {"suffix": "Helligkeit absolut", "dpt": "DPST-5-1"},
            {"suffix": "Helligkeit Status", "dpt": "DPST-5-1"},
            {"suffix": "Farbe relativ", "dpt": "DPST-3-7"},
            {"suffix": "Farbe Status", "dpt": "DPST-7-600"},
            {"suffix": "Farbe Anteil absolut", "dpt": "DPST-5-1"},
            {"suffix": "Farbe Anteil Status", "dpt": "DPST-5-1"},
        ],
        block_size=10,
        channel_type="Dimmen",
    )
    add_central(
        beleuchtung, "Zentral", "building",
        [{"suffix": "Ein/Aus", "dpt": "DPST-1-1"}], order_idx=0,
    )
    add_central(
        beleuchtung, "Zentral", "floor",
        [{"suffix": "Ein/Aus", "dpt": "DPST-1-1"}], order_idx=1,
    )

    # --- Steckdosen (Sockets) ---------------------------------------------
    steckdosen = add_category("Steckdosen", 2)
    add_point_type(
        steckdosen, "Steckdose (Schalten)",
        [{"suffix": "Schalten", "dpt": "DPST-1-1"}, {"suffix": "Schalten Status", "dpt": "DPST-1-11"}],
        block_size=5,
        channel_type="Schalten",
    )
    add_central(
        steckdosen, "Zentral", "building",
        [{"suffix": "Aus", "dpt": "DPST-1-1"}], order_idx=0,
    )

    # --- Heizung (Heating) --------------------------------------------------
    heizung = add_category("Heizung", 3)
    add_point_type(
        heizung, "Heizkreis",
        [
            {"suffix": "Temperatur", "dpt": "DPST-9-1"},
            {"suffix": "Sollwertverschiebung", "dpt": "DPST-9-2"},
            {"suffix": "Sollwertverschiebung Status", "dpt": "DPST-9-2"},
            {"suffix": "Sollwert", "dpt": "DPST-9-1"},
            {"suffix": "Sollwert Status", "dpt": "DPST-9-1"},
        ],
        block_size=5,
        channel_type="Heizung",
    )
    add_central(
        heizung, "", "building",
        [
            {"suffix": "Betriebsartumschaltung", "dpt": "DPST-20-102"},
            {"suffix": "Betriebsartumschaltung Status", "dpt": "DPST-20-102"},
        ],
        order_idx=0,
    )
    add_central(
        heizung, "Sommer/Winter", "building",
        [{"suffix": "Übersteuern", "dpt": "DPST-1-1"}],
        order_idx=1,
    )
    add_central(
        heizung, "Sommer/Winter", "floor",
        [{"suffix": "Status", "dpt": "DPST-1-1"}],
        order_idx=2,
        skip_outdoor_floors=True,
    )

    # --- Rollo (Blinds) -----------------------------------------------------
    rollo = add_category("Rollo", 4)
    add_point_type(
        rollo, "Rollo (einfach)",
        [
            {"suffix": "Auf/Ab", "dpt": "DPST-1-8"},
            {"suffix": "Stop", "dpt": "DPST-1-10"},
            {"suffix": "Position", "dpt": "DPST-5-1"},
            {"suffix": "Position Status", "dpt": "DPST-5-1"},
        ],
        block_size=5,
        channel_type="Rollo",
    )
    add_point_type(
        rollo, "Jalousie (mit Lamelle)",
        [
            {"suffix": "Auf/Ab", "dpt": "DPST-1-8"},
            {"suffix": "Stop", "dpt": "DPST-1-10"},
            {"suffix": "Position", "dpt": "DPST-5-1"},
            {"suffix": "Position Status", "dpt": "DPST-5-1"},
            {"suffix": "Lamelle", "dpt": "DPST-5-1"},
            {"suffix": "Lamelle Status", "dpt": "DPST-5-1"},
        ],
        block_size=10,
        channel_type="Rollo",
    )
    add_central(
        rollo, "Beschattung Freigabe", "building",
        [{"suffix": "", "dpt": "DPST-1-1"}], order_idx=0,
    )
    add_central(
        rollo, "Fahrzeitmessung", "floor",
        [{"suffix": "", "dpt": "DPST-1-10"}], order_idx=1,
        skip_outdoor_floors=True,
    )
    add_central(
        rollo, "Zentral", "floor",
        [
            {"suffix": "Auf/Ab", "dpt": "DPST-1-8"},
            {"suffix": "Stop", "dpt": "DPST-1-17"},
            {"suffix": "Position", "dpt": "DPST-5-1"},
        ],
        order_idx=2,
        skip_outdoor_floors=True,
    )
    # Room-level central: any room with 2+ blinds gets its own combined control block,
    # plus a single "Sperre" (lockout) address for a Langschläfer / sleep-in override.
    add_central(
        rollo, "Zentral", "room_multi",
        [
            {"suffix": "Auf/Ab", "dpt": "DPST-1-8"},
            {"suffix": "Stop", "dpt": "DPST-1-10"},
            {"suffix": "Position", "dpt": "DPST-5-1"},
        ],
        order_idx=3,
        block_size=5,
        trigger_count=2,
        skip_outdoor_floors=True,
    )
    add_central(
        rollo, "", "room_multi",
        [{"suffix": "Sperre", "dpt": "DPST-1-1"}],
        order_idx=4,
        trigger_count=2,
        skip_outdoor_floors=True,
    )

    # --- Tore (Gates/Doors) --------------------------------------------------
    tore = add_category("Tore", 5)
    add_point_type(
        tore, "Tor",
        [
            {"suffix": "Auf/Ab", "dpt": "DPST-1-8"},
            {"suffix": "Stop", "dpt": "DPST-1-10"},
            {"suffix": "Status", "dpt": "DPST-1-11"},
        ],
        block_size=5,
        channel_type="Tor",
    )


init_db()


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------
class Suffix(BaseModel):
    suffix: str
    dpt: str


class PointTypeIn(BaseModel):
    category_id: int
    name: str
    suffixes: list[Suffix]
    block_size: int = 5
    channel_type: str = ""      # must match an Actor Type's channel_type to be assignable to a circuit
    channels_needed: int = 1    # how many physical actuator channels one instance of this point needs


class CentralTemplateIn(BaseModel):
    category_id: int
    name: str
    scope: str  # 'building' | 'floor' | 'room_multi'
    suffixes: list[Suffix]
    order_idx: int = 0
    skip_outdoor_floors: bool = False
    block_size: int | None = None      # only meaningful for scope='room_multi' - pads with "res"
    trigger_count: int | None = None   # only meaningful for scope='room_multi' - min points to trigger (default 2)


class ProjectIn(BaseModel):
    name: str


class FloorIn(BaseModel):
    name: str
    is_outdoor: bool = False


class RoomIn(BaseModel):
    name: str


class RoomPointIn(BaseModel):
    point_type_id: int
    label: str = ""
    quantity: int = 1  # convenience: add N identical points at once (auto-numbered if no label)
    has_bwm: bool = False  # adds one extra "BWM" (motion sensor) address to this point


class SpecialItemIn(BaseModel):
    category_id: int
    location: str  # 'central' or floor id as string
    name: str
    suffixes: list[Suffix]


class ActorTypeIn(BaseModel):
    manufacturer: str = ""
    model: str
    channel_type: str
    channel_count: int


class ActorInstanceIn(BaseModel):
    actor_type_id: int
    floor_id: int | None = None
    location_label: str = ""
    physical_address: str = ""


class ChannelAssignIn(BaseModel):
    room_point_id: int
    channel_seq: int = 0
    actor_instance_id: int
    channel_letter: str


# --------------------------------------------------------------------------
# Categories / Point types / Central templates  ("Setup" - rarely touched)
# --------------------------------------------------------------------------
@app.get("/api/categories")
def list_categories():
    with get_db() as db:
        rows = db.execute("SELECT * FROM categories ORDER BY order_idx").fetchall()
        return [dict(r) for r in rows]


@app.get("/api/point-types")
def list_point_types():
    with get_db() as db:
        rows = db.execute("SELECT * FROM point_types ORDER BY category_id, id").fetchall()
        return [
            {
                "id": r["id"], "category_id": r["category_id"], "name": r["name"],
                "suffixes": json.loads(r["suffixes_json"]), "block_size": r["block_size"],
                "channel_type": r["channel_type"], "channels_needed": r["channels_needed"],
            }
            for r in rows
        ]


@app.post("/api/point-types")
def create_point_type(pt: PointTypeIn):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO point_types (category_id, name, suffixes_json, block_size, channel_type, channels_needed) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pt.category_id, pt.name, json.dumps([s.dict() for s in pt.suffixes]), pt.block_size,
             pt.channel_type, pt.channels_needed),
        )
        return {"id": cur.lastrowid}


@app.put("/api/point-types/{pt_id}")
def update_point_type(pt_id: int, pt: PointTypeIn):
    with get_db() as db:
        db.execute(
            "UPDATE point_types SET category_id=?, name=?, suffixes_json=?, block_size=?, "
            "channel_type=?, channels_needed=? WHERE id=?",
            (pt.category_id, pt.name, json.dumps([s.dict() for s in pt.suffixes]), pt.block_size,
             pt.channel_type, pt.channels_needed, pt_id),
        )
    return {"ok": True}


@app.delete("/api/point-types/{pt_id}")
def delete_point_type(pt_id: int):
    with get_db() as db:
        db.execute("DELETE FROM point_types WHERE id=?", (pt_id,))
    return {"ok": True}


@app.get("/api/central-templates")
def list_central_templates():
    with get_db() as db:
        rows = db.execute("SELECT * FROM central_templates ORDER BY category_id, order_idx").fetchall()
        return [
            {
                "id": r["id"], "category_id": r["category_id"], "name": r["name"],
                "scope": r["scope"], "suffixes": json.loads(r["suffixes_json"]),
                "order_idx": r["order_idx"], "skip_outdoor_floors": bool(r["skip_outdoor_floors"]),
                "block_size": r["block_size"], "trigger_count": r["trigger_count"],
            }
            for r in rows
        ]


@app.post("/api/central-templates")
def create_central_template(ct: CentralTemplateIn):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO central_templates "
            "(category_id, name, scope, suffixes_json, order_idx, skip_outdoor_floors, block_size, trigger_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (ct.category_id, ct.name, ct.scope, json.dumps([s.dict() for s in ct.suffixes]), ct.order_idx,
             int(ct.skip_outdoor_floors), ct.block_size, ct.trigger_count),
        )
        return {"id": cur.lastrowid}


@app.put("/api/central-templates/{ct_id}")
def update_central_template(ct_id: int, ct: CentralTemplateIn):
    with get_db() as db:
        db.execute(
            "UPDATE central_templates SET category_id=?, name=?, scope=?, suffixes_json=?, order_idx=?, "
            "skip_outdoor_floors=?, block_size=?, trigger_count=? WHERE id=?",
            (ct.category_id, ct.name, ct.scope, json.dumps([s.dict() for s in ct.suffixes]), ct.order_idx,
             int(ct.skip_outdoor_floors), ct.block_size, ct.trigger_count, ct_id),
        )
    return {"ok": True}


@app.delete("/api/central-templates/{ct_id}")
def delete_central_template(ct_id: int):
    with get_db() as db:
        db.execute("DELETE FROM central_templates WHERE id=?", (ct_id,))
    return {"ok": True}


# --------------------------------------------------------------------------
# Actor Types (global catalog of actuator hardware, shared across all projects)
# --------------------------------------------------------------------------
@app.get("/api/actor-types")
def list_actor_types():
    with get_db() as db:
        rows = db.execute("SELECT * FROM actor_types ORDER BY id").fetchall()
        return [
            {
                "id": r["id"], "manufacturer": r["manufacturer"], "model": r["model"],
                "channel_type": r["channel_type"], "channel_count": r["channel_count"],
            }
            for r in rows
        ]


@app.post("/api/actor-types")
def create_actor_type(at: ActorTypeIn):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO actor_types (manufacturer, model, channel_type, channel_count) VALUES (?, ?, ?, ?)",
            (at.manufacturer, at.model, at.channel_type, at.channel_count),
        )
        return {"id": cur.lastrowid}


@app.put("/api/actor-types/{at_id}")
def update_actor_type(at_id: int, at: ActorTypeIn):
    with get_db() as db:
        db.execute(
            "UPDATE actor_types SET manufacturer=?, model=?, channel_type=?, channel_count=? WHERE id=?",
            (at.manufacturer, at.model, at.channel_type, at.channel_count, at_id),
        )
    return {"ok": True}


@app.delete("/api/actor-types/{at_id}")
def delete_actor_type(at_id: int):
    with get_db() as db:
        db.execute("DELETE FROM actor_types WHERE id=?", (at_id,))
    return {"ok": True}


@app.get("/api/actor-types/export-json")
def export_actor_types_json():
    with get_db() as db:
        rows = db.execute("SELECT * FROM actor_types ORDER BY id").fetchall()
        payload = {
            "format": "knx-actor-types-v1",
            "actor_types": [
                {
                    "manufacturer": r["manufacturer"], "model": r["model"],
                    "channel_type": r["channel_type"], "channel_count": r["channel_count"],
                }
                for r in rows
            ],
        }
        buf = io.StringIO()
        buf.write(json.dumps(payload, ensure_ascii=False, indent=2))
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8")]),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="actor_types_catalog.json"'},
        )


@app.post("/api/actor-types/import-json")
def import_actor_types_json(payload: dict):
    """Upserts by (manufacturer, model): updates channel_type/channel_count if that
    combination already exists, otherwise inserts a new actor type."""
    with get_db() as db:
        imported = 0
        updated = 0
        for at in payload.get("actor_types", []):
            manufacturer = at.get("manufacturer", "")
            model = at.get("model", "")
            existing = db.execute(
                "SELECT id FROM actor_types WHERE manufacturer=? AND model=?", (manufacturer, model)
            ).fetchone()
            if existing:
                db.execute(
                    "UPDATE actor_types SET channel_type=?, channel_count=? WHERE id=?",
                    (at.get("channel_type", ""), at.get("channel_count", 1), existing["id"]),
                )
                updated += 1
            else:
                db.execute(
                    "INSERT INTO actor_types (manufacturer, model, channel_type, channel_count) VALUES (?, ?, ?, ?)",
                    (manufacturer, model, at.get("channel_type", ""), at.get("channel_count", 1)),
                )
                imported += 1
        return {"imported": imported, "updated": updated}
    return {"ok": True}


# --------------------------------------------------------------------------
# Projects / Floors / Rooms / Points
# --------------------------------------------------------------------------
@app.get("/api/projects")
def list_projects():
    with get_db() as db:
        return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY id").fetchall()]


@app.post("/api/projects")
def create_project(p: ProjectIn):
    with get_db() as db:
        try:
            cur = db.execute("INSERT INTO projects (name) VALUES (?)", (p.name,))
        except sqlite3.IntegrityError:
            raise HTTPException(400, "A project with that name already exists")
        return {"id": cur.lastrowid}


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int):
    with get_db() as db:
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))
    return {"ok": True}


@app.post("/api/projects/{project_id}/floors")
def add_floor(project_id: int, f: FloorIn):
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM floors WHERE project_id=?", (project_id,)).fetchone()
        cur = db.execute(
            "INSERT INTO floors (project_id, name, order_idx, is_outdoor) VALUES (?, ?, ?, ?)",
            (project_id, f.name, count, int(f.is_outdoor)),
        )
        return {"id": cur.lastrowid}


@app.delete("/api/floors/{floor_id}")
def delete_floor(floor_id: int):
    with get_db() as db:
        db.execute("DELETE FROM floors WHERE id=?", (floor_id,))
    return {"ok": True}


@app.post("/api/floors/{floor_id}/rooms")
def add_room(floor_id: int, r: RoomIn):
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM rooms WHERE floor_id=?", (floor_id,)).fetchone()
        cur = db.execute(
            "INSERT INTO rooms (floor_id, name, order_idx) VALUES (?, ?, ?)",
            (floor_id, r.name, count),
        )
        return {"id": cur.lastrowid}


@app.delete("/api/rooms/{room_id}")
def delete_room(room_id: int):
    with get_db() as db:
        db.execute("DELETE FROM rooms WHERE id=?", (room_id,))
    return {"ok": True}


@app.post("/api/rooms/{room_id}/points")
def add_room_point(room_id: int, rp: RoomPointIn):
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM room_points WHERE room_id=?", (room_id,)).fetchone()
        ids = []
        for i in range(max(1, rp.quantity)):
            label = rp.label
            if not label and rp.quantity > 1:
                label = str(i + 1)
            cur = db.execute(
                "INSERT INTO room_points (room_id, point_type_id, label, order_idx, has_bwm) VALUES (?, ?, ?, ?, ?)",
                (room_id, rp.point_type_id, label, count + i, int(rp.has_bwm)),
            )
            ids.append(cur.lastrowid)
        return {"ids": ids}


@app.delete("/api/room-points/{rp_id}")
def delete_room_point(rp_id: int):
    with get_db() as db:
        db.execute("DELETE FROM room_points WHERE id=?", (rp_id,))
    return {"ok": True}


@app.get("/api/projects/{project_id}/tree")
def get_project_tree(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")
        floors = db.execute(
            "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall()
        result = {"id": project["id"], "name": project["name"], "floors": []}
        for f in floors:
            rooms = db.execute(
                "SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (f["id"],)
            ).fetchall()
            room_list = []
            for r in rooms:
                points = db.execute(
                    "SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (r["id"],)
                ).fetchall()
                room_list.append(
                    {
                        "id": r["id"], "name": r["name"],
                        "points": [
                            {
                                "id": p["id"], "point_type_id": p["point_type_id"], "label": p["label"],
                                "has_bwm": bool(p["has_bwm"]),
                            }
                            for p in points
                        ],
                    }
                )
            result["floors"].append(
                {"id": f["id"], "name": f["name"], "is_outdoor": bool(f["is_outdoor"]), "rooms": room_list}
            )
        return result


@app.get("/api/projects/{project_id}/specials")
def list_specials(project_id: int):
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM special_items WHERE project_id=? ORDER BY category_id, order_idx", (project_id,)
        ).fetchall()
        return [
            {
                "id": r["id"], "category_id": r["category_id"], "location": r["location"],
                "name": r["name"], "suffixes": json.loads(r["suffixes_json"]),
            }
            for r in rows
        ]


@app.post("/api/projects/{project_id}/specials")
def add_special(project_id: int, s: SpecialItemIn):
    with get_db() as db:
        (count,) = db.execute("SELECT COUNT(*) FROM special_items WHERE project_id=?", (project_id,)).fetchone()
        cur = db.execute(
            "INSERT INTO special_items (project_id, category_id, location, name, suffixes_json, order_idx) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, s.category_id, s.location, s.name, json.dumps([x.dict() for x in s.suffixes]), count),
        )
        return {"id": cur.lastrowid}


@app.delete("/api/specials/{special_id}")
def delete_special(special_id: int):
    with get_db() as db:
        db.execute("DELETE FROM special_items WHERE id=?", (special_id,))
    return {"ok": True}


# --------------------------------------------------------------------------
# Project backup / duplicate / transfer (JSON) - separate from the ETS CSV export
# --------------------------------------------------------------------------
@app.get("/api/projects/{project_id}/export-json")
def export_project_json(project_id: int):
    """
    Full project definition as JSON: floors, rooms, points, and specials.
    References point types / categories by NAME (not internal id) so this file
    can be re-imported on a different install even if ids don't line up,
    as long as the same Point Types / Categories exist there.
    """
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        categories = {r["id"]: r["name"] for r in db.execute("SELECT * FROM categories").fetchall()}
        point_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM point_types").fetchall()}

        floors_out = []
        for floor in db.execute(
            "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall():
            rooms_out = []
            for room in db.execute(
                "SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)
            ).fetchall():
                points_out = []
                for point in db.execute(
                    "SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (room["id"],)
                ).fetchall():
                    pt = point_types.get(point["point_type_id"])
                    if not pt:
                        continue
                    points_out.append(
                        {
                            "point_type_name": pt["name"],
                            "category_name": categories.get(pt["category_id"], ""),
                            "label": point["label"],
                            "has_bwm": bool(point["has_bwm"]),
                        }
                    )
                rooms_out.append({"name": room["name"], "points": points_out})
            floors_out.append({"name": floor["name"], "is_outdoor": bool(floor["is_outdoor"]), "rooms": rooms_out})

        floor_order_by_id = {}
        for floor in db.execute(
            "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall():
            floor_order_by_id[floor["id"]] = floor["order_idx"]

        specials_out = []
        for s in db.execute(
            "SELECT * FROM special_items WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall():
            location = s["location"]
            if location != "central" and location.isdigit() and int(location) in floor_order_by_id:
                location = f"floor:{floor_order_by_id[int(location)]}"
            specials_out.append(
                {
                    "category_name": categories.get(s["category_id"], ""),
                    "location": location,
                    "name": s["name"],
                    "suffixes": json.loads(s["suffixes_json"]),
                }
            )

        payload = {"format": "knx-ga-project-v1", "project_name": project["name"], "floors": floors_out, "specials": specials_out}
        buf = io.StringIO()
        buf.write(json.dumps(payload, ensure_ascii=False, indent=2))
        buf.seek(0)
        filename = f"{project['name'].replace(' ', '_')}_backup.json"
        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8")]),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


@app.post("/api/projects/import-json")
def import_project_json(payload: dict):
    """
    Recreates a project from a file produced by export-json. Matches Point Types
    and Categories by name against what already exists on this install - anything
    that doesn't match is skipped (not silently guessed at).
    If a project with the same name already exists, the import is saved under
    "<name> (imported)" instead of overwriting it.
    """
    with get_db() as db:
        name = payload.get("project_name", "Imported Project")
        existing = db.execute("SELECT id FROM projects WHERE name=?", (name,)).fetchone()
        if existing:
            name = f"{name} (imported)"

        categories_by_name = {r["name"]: r["id"] for r in db.execute("SELECT * FROM categories").fetchall()}
        point_types_by_name = {
            (r["category_id"], r["name"]): r["id"] for r in db.execute("SELECT * FROM point_types").fetchall()
        }

        cur = db.execute("INSERT INTO projects (name) VALUES (?)", (name,))
        project_id = cur.lastrowid
        skipped = []

        floor_id_map = {}  # index in payload -> new floor id, for resolving special locations
        for f_idx, floor in enumerate(payload.get("floors", [])):
            fcur = db.execute(
                "INSERT INTO floors (project_id, name, order_idx, is_outdoor) VALUES (?, ?, ?, ?)",
                (project_id, floor["name"], f_idx, int(floor.get("is_outdoor", False))),
            )
            floor_id = fcur.lastrowid
            floor_id_map[f_idx] = floor_id
            for r_idx, room in enumerate(floor.get("rooms", [])):
                rcur = db.execute(
                    "INSERT INTO rooms (floor_id, name, order_idx) VALUES (?, ?, ?)",
                    (floor_id, room["name"], r_idx),
                )
                room_id = rcur.lastrowid
                for p_idx, point in enumerate(room.get("points", [])):
                    cat_id = categories_by_name.get(point.get("category_name"))
                    pt_id = point_types_by_name.get((cat_id, point.get("point_type_name")))
                    if not pt_id:
                        skipped.append(f"{room['name']}: {point.get('point_type_name')}")
                        continue
                    db.execute(
                        "INSERT INTO room_points (room_id, point_type_id, label, order_idx, has_bwm) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (room_id, pt_id, point.get("label", ""), p_idx, int(point.get("has_bwm", False))),
                    )

        for s_idx, special in enumerate(payload.get("specials", [])):
            cat_id = categories_by_name.get(special.get("category_name"))
            if not cat_id:
                skipped.append(f"special: {special.get('name')}")
                continue
            location = special.get("location", "central")
            if isinstance(location, str) and location.startswith("floor:"):
                floor_pos = int(location.split(":", 1)[1])
                location = str(floor_id_map.get(floor_pos, "central"))
            db.execute(
                "INSERT INTO special_items (project_id, category_id, location, name, suffixes_json, order_idx) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, cat_id, location, special.get("name", ""),
                 json.dumps(special.get("suffixes", [])), s_idx),
            )

        return {"id": project_id, "name": name, "skipped": skipped}


# --------------------------------------------------------------------------
# Actor Instances (physical devices placed in a project) + Circuits (Abgangsliste)
# --------------------------------------------------------------------------
@app.get("/api/projects/{project_id}/actor-instances")
def list_actor_instances(project_id: int):
    with get_db() as db:
        actor_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM actor_types").fetchall()}
        floors = {r["id"]: r["name"] for r in db.execute("SELECT * FROM floors WHERE project_id=?", (project_id,)).fetchall()}
        rows = db.execute(
            "SELECT * FROM actor_instances WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall()
        result = []
        for r in rows:
            at = actor_types.get(r["actor_type_id"], {})
            used = db.execute(
                "SELECT channel_letter FROM channel_assignments WHERE actor_instance_id=?", (r["id"],)
            ).fetchall()
            used_letters = {u["channel_letter"] for u in used}
            result.append(
                {
                    "id": r["id"], "actor_type_id": r["actor_type_id"],
                    "actor_type_name": join_parts(at.get("manufacturer", ""), at.get("model", "")) or "?",
                    "channel_type": at.get("channel_type", ""), "channel_count": at.get("channel_count", 0),
                    "floor_id": r["floor_id"], "floor_name": floors.get(r["floor_id"], ""),
                    "location_label": r["location_label"], "physical_address": r["physical_address"],
                    "channels_used": len(used_letters), "channels_free": at.get("channel_count", 0) - len(used_letters),
                }
            )
        return result


@app.post("/api/projects/{project_id}/actor-instances")
def add_actor_instance(project_id: int, ai: ActorInstanceIn):
    with get_db() as db:
        (count,) = db.execute(
            "SELECT COUNT(*) FROM actor_instances WHERE project_id=?", (project_id,)
        ).fetchone()
        cur = db.execute(
            "INSERT INTO actor_instances (project_id, actor_type_id, floor_id, location_label, physical_address, order_idx) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, ai.actor_type_id, ai.floor_id, ai.location_label, ai.physical_address, count),
        )
        return {"id": cur.lastrowid}


@app.delete("/api/actor-instances/{ai_id}")
def delete_actor_instance(ai_id: int):
    with get_db() as db:
        db.execute("DELETE FROM actor_instances WHERE id=?", (ai_id,))
    return {"ok": True}


def get_circuits(db, project_id):
    """
    Every physical output ("circuit") the project needs: one entry per channel a
    room_point requires (usually 1, but channels_needed can be >1 for e.g. a
    tunable-white driver needing 2 physical dimming channels).
    """
    point_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM point_types").fetchall()}
    actor_instances = {r["id"]: dict(r) for r in db.execute("SELECT * FROM actor_instances WHERE project_id=?", (project_id,)).fetchall()}
    actor_types = {r["id"]: dict(r) for r in db.execute("SELECT * FROM actor_types").fetchall()}
    assignments = {
        (a["room_point_id"], a["channel_seq"]): dict(a)
        for a in db.execute("SELECT * FROM channel_assignments WHERE project_id=?", (project_id,)).fetchall()
    }

    circuits = []
    floors = db.execute("SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)).fetchall()
    for floor in floors:
        rooms = db.execute("SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)).fetchall()
        for room in rooms:
            points = db.execute(
                "SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (room["id"],)
            ).fetchall()
            for point in points:
                pt = point_types.get(point["point_type_id"])
                if not pt or not pt["channel_type"]:
                    continue  # this point type has no physical channel configured
                base_name = join_parts(room["name"], point["label"])
                for seq in range(pt["channels_needed"]):
                    fn_name = base_name if pt["channels_needed"] == 1 else f"{base_name} ({seq + 1})"
                    key = (point["id"], seq)
                    assignment = assignments.get(key)
                    assignment_info = None
                    if assignment:
                        ai = actor_instances.get(assignment["actor_instance_id"])
                        at = actor_types.get(ai["actor_type_id"]) if ai else None
                        assignment_info = {
                            "actor_instance_id": assignment["actor_instance_id"],
                            "channel_letter": assignment["channel_letter"],
                            "actor_name": join_parts(at.get("manufacturer", ""), at.get("model", "")) if at else "?",
                            "location_label": ai["location_label"] if ai else "",
                            "physical_address": ai["physical_address"] if ai else "",
                        }
                    circuits.append(
                        {
                            "room_point_id": point["id"], "channel_seq": seq,
                            "floor_id": floor["id"], "floor_name": floor["name"], "room_name": room["name"],
                            "function_name": fn_name, "point_type_name": pt["name"],
                            "channel_type": pt["channel_type"], "assignment": assignment_info,
                        }
                    )
    return circuits


@app.get("/api/projects/{project_id}/circuits")
def list_circuits(project_id: int):
    with get_db() as db:
        return get_circuits(db, project_id)


@app.post("/api/projects/{project_id}/circuits/assign")
def assign_circuit(project_id: int, a: ChannelAssignIn):
    with get_db() as db:
        # Free up this circuit's previous assignment, if any (moving it to a new channel).
        db.execute(
            "DELETE FROM channel_assignments WHERE room_point_id=? AND channel_seq=?",
            (a.room_point_id, a.channel_seq),
        )
        taken = db.execute(
            "SELECT 1 FROM channel_assignments WHERE actor_instance_id=? AND channel_letter=?",
            (a.actor_instance_id, a.channel_letter),
        ).fetchone()
        if taken:
            raise HTTPException(400, f"Channel {a.channel_letter} is already assigned to something else")
        db.execute(
            "INSERT INTO channel_assignments (project_id, room_point_id, channel_seq, actor_instance_id, channel_letter) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, a.room_point_id, a.channel_seq, a.actor_instance_id, a.channel_letter),
        )
    return {"ok": True}


@app.delete("/api/projects/{project_id}/circuits/{room_point_id}/{channel_seq}")
def unassign_circuit(project_id: int, room_point_id: int, channel_seq: int):
    with get_db() as db:
        db.execute(
            "DELETE FROM channel_assignments WHERE room_point_id=? AND channel_seq=?",
            (room_point_id, channel_seq),
        )
    return {"ok": True}


@app.post("/api/projects/{project_id}/circuits/auto-assign")
def auto_assign_circuits(project_id: int):
    """Fills every unassigned circuit into the first free matching-type channel available,
    in floor/room order. Does not touch circuits that are already assigned."""
    with get_db() as db:
        circuits = get_circuits(db, project_id)
        actor_instances = db.execute(
            "SELECT ai.*, at.channel_type as ct, at.channel_count as cc "
            "FROM actor_instances ai JOIN actor_types at ON ai.actor_type_id = at.id "
            "WHERE ai.project_id=? ORDER BY ai.order_idx",
            (project_id,),
        ).fetchall()

        used_by_actor = {}
        for row in db.execute(
            "SELECT actor_instance_id, channel_letter FROM channel_assignments WHERE project_id=?", (project_id,)
        ).fetchall():
            used_by_actor.setdefault(row["actor_instance_id"], set()).add(row["channel_letter"])

        assigned_count = 0
        unassigned = []
        for circuit in circuits:
            if circuit["assignment"]:
                continue
            placed = False
            for ai in actor_instances:
                if ai["ct"] != circuit["channel_type"]:
                    continue
                used = used_by_actor.setdefault(ai["id"], set())
                for letter in channel_letters(ai["cc"]):
                    if letter not in used:
                        db.execute(
                            "INSERT INTO channel_assignments "
                            "(project_id, room_point_id, channel_seq, actor_instance_id, channel_letter) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (project_id, circuit["room_point_id"], circuit["channel_seq"], ai["id"], letter),
                        )
                        used.add(letter)
                        assigned_count += 1
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                unassigned.append(f"{circuit['floor_name']} / {circuit['function_name']} ({circuit['channel_type']})")

        return {"assigned": assigned_count, "unassigned": unassigned}


@app.get("/api/projects/{project_id}/export-abgangsliste.csv")
def export_abgangsliste(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        circuits = get_circuits(db, project_id)
        by_room_point = {(c["room_point_id"], c["channel_seq"]): c for c in circuits}

        actor_instances = db.execute(
            "SELECT ai.*, at.channel_type as ct, at.channel_count as cc, "
            "at.manufacturer as at_manufacturer, at.model as at_model "
            "FROM actor_instances ai JOIN actor_types at ON ai.actor_type_id = at.id "
            "WHERE ai.project_id=? ORDER BY ai.order_idx",
            (project_id,),
        ).fetchall()
        floors = {r["id"]: r["name"] for r in db.execute("SELECT * FROM floors WHERE project_id=?", (project_id,)).fetchall()}
        assignments = db.execute(
            "SELECT * FROM channel_assignments WHERE project_id=?", (project_id,)
        ).fetchall()

        buf = io.StringIO()
        writer = csv.writer(buf, delimiter="\t", quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(["Geschoss", "Raum/UV", "Aktor", "Physikalische Adr.", "Kanal", "Funktion"])

        for ai in actor_instances:
            by_letter = {}
            for a in assignments:
                if a["actor_instance_id"] == ai["id"]:
                    circuit = by_room_point.get((a["room_point_id"], a["channel_seq"]))
                    by_letter[a["channel_letter"]] = circuit["function_name"] if circuit else "?"

            actor_display = join_parts(ai["at_manufacturer"], ai["at_model"])
            for i, letter in enumerate(channel_letters(ai["cc"])):
                first_row = i == 0
                writer.writerow(
                    [
                        floors.get(ai["floor_id"], "") if first_row else "",
                        ai["location_label"] if first_row else "",
                        actor_display if first_row else "",
                        ai["physical_address"] if first_row else "",
                        letter,
                        by_letter.get(letter, "RESERVE"),
                    ]
                )

        buf.seek(0)
        filename = f"{project['name'].replace(' ', '_')}_abgangsliste.csv"
        return StreamingResponse(
            iter([buf.getvalue().encode("iso-8859-1", errors="replace")]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------
def build_ga_tree(project_id: int):
    with get_db() as db:
        project = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not project:
            raise HTTPException(404, "Project not found")

        categories = db.execute("SELECT * FROM categories ORDER BY order_idx").fetchall()
        point_types = {
            r["id"]: {
                "category_id": r["category_id"], "name": r["name"],
                "suffixes": json.loads(r["suffixes_json"]), "block_size": r["block_size"],
            }
            for r in db.execute("SELECT * FROM point_types").fetchall()
        }
        floors = db.execute(
            "SELECT * FROM floors WHERE project_id=? ORDER BY order_idx", (project_id,)
        ).fetchall()
        specials_by_cat = {}
        for r in db.execute("SELECT * FROM special_items WHERE project_id=? ORDER BY order_idx", (project_id,)):
            specials_by_cat.setdefault(r["category_id"], []).append(
                {"location": r["location"], "name": r["name"], "suffixes": json.loads(r["suffixes_json"])}
            )

        # Which categories actually have at least one point anywhere in this project?
        # Categories with no usage and no specials are skipped entirely (e.g. no Steckdosen
        # in the project -> no Steckdosen Main Group / central function generated).
        used_category_ids = set(specials_by_cat.keys())
        for floor in floors:
            for room in db.execute("SELECT * FROM rooms WHERE floor_id=?", (floor["id"],)).fetchall():
                for point in db.execute("SELECT * FROM room_points WHERE room_id=?", (room["id"],)).fetchall():
                    pt = point_types.get(point["point_type_id"])
                    if pt:
                        used_category_ids.add(pt["category_id"])

        main_groups = []
        for main_idx, cat in enumerate(categories):
            cat_id = cat["id"]

            if not cat["is_allgemein"] and cat_id not in used_category_ids:
                continue  # category unused in this project - skip its Main Group entirely

            central_templates = [
                dict(t) for t in db.execute(
                    "SELECT * FROM central_templates WHERE category_id=? ORDER BY order_idx", (cat_id,)
                ).fetchall()
            ]
            middles = []

            if cat["is_allgemein"]:
                # Each 'building' scope central template becomes its own Middle Group.
                for middle_idx, tmpl in enumerate(central_templates):
                    suffixes = json.loads(tmpl["suffixes_json"])
                    subs = [
                        {"sub": i, "name": f"{s['suffix']}", "dpt": s["dpt"]}
                        for i, s in enumerate(suffixes)
                    ]
                    middles.append({"middle": middle_idx, "name": tmpl["name"], "subs": subs})

            else:
                # Middle 0: Zentralfunktionen (building-scope + one block per floor + special 'central' items)
                central_subs = []
                sub_idx = 0
                for tmpl in central_templates:
                    suffixes = json.loads(tmpl["suffixes_json"])
                    if tmpl["scope"] == "building":
                        for s in suffixes:
                            central_subs.append({"sub": sub_idx, "name": f"{tmpl['name']} {s['suffix']}".strip(), "dpt": s["dpt"]})
                            sub_idx += 1
                    elif tmpl["scope"] == "floor":
                        for floor in floors:
                            if tmpl["skip_outdoor_floors"] and floor["is_outdoor"]:
                                continue
                            for s in suffixes:
                                central_subs.append(
                                    {"sub": sub_idx, "name": f"{tmpl['name']} {floor['name']} {s['suffix']}".strip(), "dpt": s["dpt"]}
                                )
                                sub_idx += 1

                # room_multi scope: one block per room that has >= trigger_count points in this category
                room_multi_templates = [t for t in central_templates if t["scope"] == "room_multi"]
                if room_multi_templates:
                    for floor in floors:
                        rooms_here = db.execute(
                            "SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)
                        ).fetchall()
                        for room in rooms_here:
                            room_points_here = db.execute(
                                "SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (room["id"],)
                            ).fetchall()
                            count_in_cat = sum(
                                1 for p in room_points_here
                                if point_types.get(p["point_type_id"], {}).get("category_id") == cat_id
                            )
                            for tmpl in room_multi_templates:
                                if tmpl["skip_outdoor_floors"] and floor["is_outdoor"]:
                                    continue
                                trigger = tmpl["trigger_count"] or 2
                                if count_in_cat < trigger:
                                    continue
                                suffixes = json.loads(tmpl["suffixes_json"])
                                prefix = join_parts(room["name"], tmpl["name"])
                                used = 0
                                for s in suffixes:
                                    central_subs.append(
                                        {"sub": sub_idx, "name": join_parts(prefix, s["suffix"]), "dpt": s["dpt"]}
                                    )
                                    sub_idx += 1
                                    used += 1
                                if tmpl["block_size"]:
                                    for _ in range(max(0, tmpl["block_size"] - used)):
                                        central_subs.append(
                                            {"sub": sub_idx, "name": join_parts(prefix, "res"), "dpt": ""}
                                        )
                                        sub_idx += 1

                for special in specials_by_cat.get(cat_id, []):
                    if special["location"] == "central":
                        for s in special["suffixes"]:
                            central_subs.append({"sub": sub_idx, "name": f"{special['name']} {s['suffix']}".strip(), "dpt": s["dpt"]})
                            sub_idx += 1

                if central_subs:
                    middles.append({"middle": 0, "name": "Zentralfunktionen", "subs": central_subs})

                # Middle 1..n: one per floor
                for floor_pos, floor in enumerate(floors):
                    middle_idx = floor_pos + (1 if central_subs else 0)
                    rooms = db.execute(
                        "SELECT * FROM rooms WHERE floor_id=? ORDER BY order_idx", (floor["id"],)
                    ).fetchall()
                    subs = []
                    sub_idx = 0
                    for room in rooms:
                        points = db.execute(
                            "SELECT * FROM room_points WHERE room_id=? ORDER BY order_idx", (room["id"],)
                        ).fetchall()
                        for point in points:
                            pt = point_types.get(point["point_type_id"])
                            if not pt or pt["category_id"] != cat_id:
                                continue
                            label = point["label"]
                            prefix = f"{room['name']} {label}".strip() if label else room["name"]
                            point_suffixes = list(pt["suffixes"])
                            if point["has_bwm"]:
                                point_suffixes = point_suffixes + [{"suffix": "BWM", "dpt": "DPST-1-1"}]
                            used = 0
                            for s in point_suffixes:
                                if sub_idx > 255:
                                    raise HTTPException(400, f"Floor '{floor['name']}' / '{cat['name']}' exceeds 256 Sub Groups.")
                                subs.append({"sub": sub_idx, "name": f"{prefix} {s['suffix']}", "dpt": s["dpt"]})
                                sub_idx += 1
                                used += 1
                            for _ in range(max(0, pt["block_size"] - used)):
                                if sub_idx > 255:
                                    raise HTTPException(400, f"Floor '{floor['name']}' / '{cat['name']}' exceeds 256 Sub Groups.")
                                subs.append({"sub": sub_idx, "name": f"{prefix} res", "dpt": ""})
                                sub_idx += 1
                    for special in specials_by_cat.get(cat_id, []):
                        if special["location"] == str(floor["id"]):
                            for s in special["suffixes"]:
                                subs.append({"sub": sub_idx, "name": f"{special['name']} {s['suffix']}".strip(), "dpt": s["dpt"]})
                                sub_idx += 1
                    if subs:
                        middles.append({"middle": middle_idx, "name": floor["name"], "subs": subs})

            if middles:
                main_groups.append({"main": main_idx, "name": cat["name"], "middles": middles})

        return {"project_name": project["name"], "main_groups": main_groups}


@app.get("/api/projects/{project_id}/preview")
def preview_ga(project_id: int):
    return build_ga_tree(project_id)


@app.get("/api/projects/{project_id}/export.csv")
def export_csv(project_id: int):
    data = build_ga_tree(project_id)

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t", quotechar='"', quoting=csv.QUOTE_ALL)

    writer.writerow(
        ["Main", "Middle", "Sub", "Address", "Central", "Unfiltered", "Description", "DatapointType", "Security"]
    )

    for main in data["main_groups"]:
        writer.writerow([main["name"], "", "", f"{main['main']}/-/-", "", "", "", "", "Auto"])
        for middle in main["middles"]:
            writer.writerow(["", middle["name"], "", f"{main['main']}/{middle['middle']}/-", "", "", "", "", "Auto"])
            for sub in middle["subs"]:
                writer.writerow(
                    [
                        "", "", sub["name"],
                        f"{main['main']}/{middle['middle']}/{sub['sub']}",
                        "", "", "", sub["dpt"], "Auto",
                    ]
                )

    buf.seek(0)
    filename = f"{data['project_name'].replace(' ', '_')}_group_addresses.csv"
    return StreamingResponse(
        iter([buf.getvalue().encode("iso-8859-1", errors="replace")]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
