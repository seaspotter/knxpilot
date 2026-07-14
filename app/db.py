"""
Database layer: connection helper, schema creation, lightweight migrations
for existing installs, and the default seed data (categories, point types,
central templates) derived from analysis of real ETS6 exports.
"""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "knx_ga.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


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

            -- Physical device catalog (global, shared across every project): actuators,
            -- sensors, weather stations, touch panels, etc. channel_type/channel_count are
            -- only meaningful for devices in the "Aktor" group (see group_name).
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

            -- Which devices (any group - sensor, touch panel, weather station, actuator...)
            -- are planned for a given room. Separate from channel wiring - this is a simple
            -- "what goes where, how many" planning list, used to build a project-wide bill
            -- of materials (device-summary endpoint).
            CREATE TABLE IF NOT EXISTS room_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
                device_type_id INTEGER NOT NULL REFERENCES actor_types(id),
                quantity INTEGER NOT NULL DEFAULT 1,
                note TEXT NOT NULL DEFAULT '',
                order_idx INTEGER NOT NULL DEFAULT 0
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
        # Guarded because the table rebuild below removes the "name" column entirely once
        # it has run - without this check, every restart after that would crash trying to
        # reference a column that no longer exists.
        actor_types_cols = [r["name"] for r in db.execute("PRAGMA table_info(actor_types)").fetchall()]
        if "name" in actor_types_cols:
            db.execute("UPDATE actor_types SET model = name WHERE model = '' AND name != ''")

        # One-time table rebuild: add group_name/description and make channel_count nullable
        # (channels only apply to the "Aktor" group - sensors, weather stations, touch panels
        # etc. don't have them). SQLite can't relax a NOT NULL constraint via ALTER TABLE, so
        # this recreates the table, preserving every existing row's id (actor_instances.actor_type_id
        # keeps pointing at the same rows).
        cols = [r["name"] for r in db.execute("PRAGMA table_info(actor_types)").fetchall()]
        if "group_name" not in cols:
            # PRAGMA foreign_keys is a no-op while a transaction is open, so commit first -
            # otherwise it silently stays enabled and the DROP TABLE below fails against any
            # actor_instances rows that reference this table (real "FOREIGN KEY constraint failed").
            db.commit()
            db.execute("PRAGMA foreign_keys = OFF")
            db.executescript(
                """
                DROP TABLE IF EXISTS actor_types_new;
                CREATE TABLE actor_types_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manufacturer TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    group_name TEXT NOT NULL DEFAULT 'Aktor',
                    description TEXT NOT NULL DEFAULT '',
                    channel_type TEXT NOT NULL DEFAULT '',
                    channel_count INTEGER
                );
                INSERT INTO actor_types_new (id, manufacturer, model, channel_type, channel_count)
                    SELECT id, manufacturer, model, channel_type, channel_count FROM actor_types;
                DROP TABLE actor_types;
                ALTER TABLE actor_types_new RENAME TO actor_types;
                """
            )
            db.commit()
            db.execute("PRAGMA foreign_keys = ON")

        (count,) = db.execute("SELECT COUNT(*) FROM categories").fetchone()
        if count == 0:
            seed_defaults(db)

        (count,) = db.execute("SELECT COUNT(*) FROM actor_types").fetchone()
        if count == 0:
            seed_default_actor_types(db)


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
        channel_type="LED",
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


# (manufacturer, model, group_name, description, channel_type, channel_count)
DEFAULT_ACTOR_TYPES = [
    ('MDT', 'AKH-0400.03', 'Aktor', 'Heizungsaktor 4 Kanäle', 'Heizung', 4),
    ('MDT', 'AKH-0600.03', 'Aktor', 'Heizungsaktor 6 Kanäle', 'Heizung', 6),
    ('MDT', 'AKH-0800.03', 'Aktor', 'Heizungsaktor 8 Kanäle', 'Heizung', 8),
    ('MDT', 'BE-04000.02', 'Aktor', 'Binäreingang 4 Kanäle (potentialfrei)', 'Binäreingang', 4),
    ('MDT', 'BE-04024.02', 'Aktor', 'Binäreingang 4 Kanäle (24V)', 'Binäreingang', 4),
    ('MDT', 'BE-04230.02', 'Aktor', 'Binäreingang 4 Kanäle (230V)', 'Binäreingang', 4),
    ('MDT', 'BE-08000.02', 'Aktor', 'Binäreingang 8 Kanäle (potentialfrei)', 'Binäreingang', 8),
    ('MDT', 'BE-08024.02', 'Aktor', 'Binäreingang 8 Kanäle (24V)', 'Binäreingang', 8),
    ('MDT', 'BE-08230.02', 'Aktor', 'Binäreingang 8 Kanäle (230V)', 'Binäreingang', 8),
    ('MDT', 'BE-16000.02', 'Aktor', 'Binäreingang 16 Kanäle (potentialfrei)', 'Binäreingang', 16),
    ('MDT', 'BE-16024.02', 'Aktor', 'Binäreingang 16 Kanäle (24V)', 'Binäreingang', 16),
    ('MDT', 'BE-16230.02', 'Aktor', 'Binäreingang 16 Kanäle (230V)', 'Binäreingang', 16),
    ('MDT', 'BE-32000.02', 'Aktor', 'Binäreingang 32 Kanäle (potentialfrei)', 'Binäreingang', 32),
    ('MDT', 'BE-GTS06TW.01S', 'Bedienelement', 'Glas Touch Smart 6 Zoll Weiß', '', None),
    ('MDT', 'BE-GTS06TS.01S', 'Bedienelement', 'Glas Touch Smart 6 Zoll Schwarz', '', None),
    ('MDT', 'BE-GTSP6TW.01S', 'Bedienelement', 'Glas Touch Smart Plus 6 Zoll Weiß', '', None),
    ('MDT', 'BE-GTSP6TS.01S', 'Bedienelement', 'Glas Touch Smart Plus 6 Zoll Schwarz', '', None),
    ('MDT', 'BE-GT20W.02', 'Bedienelement', 'Glastaster II Smart Weiß', '', None),
    ('MDT', 'BE-GT20S.02S', 'Bedienelement', 'Glastaster II Smart Schwarz', '', None),
    ('MDT', 'BE-GT2TW.02', 'Bedienelement', 'Glastaster II Smart Weiß mit Temperatursensor', '', None),
    ('MDT', 'BE-GT2TS.02S', 'Bedienelement', 'Glastaster II Smart Schwarz mit Temperatursensor', '', None),
    ('MDT', 'BE-TAS6304.01', 'Bedienelement', 'Taster Smart 63 4-fach', '', None),
    ('MDT', 'BE-TAS63T4.01', 'Bedienelement', 'Taster Smart 63 4-fach mit Temperatursensor', '', None),
    ('MDT', 'BE-TAL6301.01', 'Bedienelement', 'Taster Light 63 1-fach', '', None),
    ('MDT', 'BE-TAL63T1.01', 'Bedienelement', 'Taster Light 63 1-fach mit Temperatursensor', '', None),
    ('MDT', 'BE-TAL6301.A1', 'Bedienelement', 'Taster Light 63 1-fach (Auf/Ab)', '', None),
    ('MDT', 'BE-TAL63T1.A1', 'Bedienelement', 'Taster Light 63 1-fach (Auf/Ab) mit Temperatursensor', '', None),
    ('MDT', 'BE-TAL6301.B1', 'Bedienelement', 'Taster Light 63 1-fach (I/O)', '', None),
    ('MDT', 'BE-TAL63T1.B1', 'Bedienelement', 'Taster Light 63 1-fach (I/O) mit Temperatursensor', '', None),
    ('MDT', 'BE-TAL6302.01', 'Bedienelement', 'Taster Light 63 2-fach', '', None),
    ('MDT', 'BE-TAL63T2.01', 'Bedienelement', 'Taster Light 63 2-fach mit Temperatursensor', '', None),
    ('MDT', 'BE-TAL6302.A1', 'Bedienelement', 'Taster Light 63 2-fach (Auf/Ab)', '', None),
    ('MDT', 'BE-TAL63T2.A1', 'Bedienelement', 'Taster Light 63 2-fach (Auf/Ab) mit Temperatursensor', '', None),
    ('MDT', 'BE-TAL6302.B1', 'Bedienelement', 'Taster Light 63 2-fach (I/O)', '', None),
    ('MDT', 'BE-TAL63T2.B1', 'Bedienelement', 'Taster Light 63 2-fach (I/O) mit Temperatursensor', '', None),
    ('MDT', 'BE-TAL6302.C1', 'Bedienelement', 'Taster Light 63 2-fach (Auf/Ab, I/O)', '', None),
    ('MDT', 'BE-TAL63T2.C1', 'Bedienelement', 'Taster Light 63 2-fach (Auf/Ab, I/O) mit Temperatursensor', '', None),
    ('MDT', 'BE-TAL6302.D1', 'Bedienelement', 'Taster Light 63 2-fach (I/O, Auf/Ab)', '', None),
    ('MDT', 'BE-TAL6304.01', 'Bedienelement', 'Taster Light 63 4-fach', '', None),
    ('MDT', 'BE-TAL63T4.01', 'Bedienelement', 'Taster Light 63 4-fach mit Temperatursensor', '', None),
    ('MDT', 'AKS-0216.03', 'Aktor', 'Schaltaktor Standard 2 Kanäle', 'Schalten', 2),
    ('MDT', 'AKS-0416.03', 'Aktor', 'Schaltaktor Standard 4 Kanäle', 'Schalten', 4),
    ('MDT', 'AKS-0816.03', 'Aktor', 'Schaltaktor Standard 8 Kanäle', 'Schalten', 8),
    ('MDT', 'AKS-1216.03', 'Aktor', 'Schaltaktor Standard 12 Kanäle', 'Schalten', 12),
    ('MDT', 'AKS-1616.03', 'Aktor', 'Schaltaktor Standard 16 Kanäle', 'Schalten', 16),
    ('MDT', 'AKS-2016.03', 'Aktor', 'Schaltaktor Standard 20 Kanäle', 'Schalten', 20),
    ('MDT', 'AKS-2416.03', 'Aktor', 'Schaltaktor Standard 24 Kanäle', 'Schalten', 24),
    ('MDT', 'AKK-0216.03', 'Aktor', 'Schaltaktor Kompakt 2 Kanäle', 'Schalten', 2),
    ('MDT', 'AKK-0416.03', 'Aktor', 'Schaltaktor Kompakt 4 Kanäle', 'Schalten', 4),
    ('MDT', 'AKK-0816.03', 'Aktor', 'Schaltaktor Kompakt 8 Kanäle', 'Schalten', 8),
    ('MDT', 'AKK-1616.03', 'Aktor', 'Schaltaktor Kompakt 16 Kanäle', 'Schalten', 16),
    ('MDT', 'AKK-2416.03', 'Aktor', 'Schaltaktor Kompakt 24 Kanäle', 'Schalten', 24),
    ('MDT', 'JAL-0210.02', 'Aktor', 'Jalousieaktor 2 Kanäle', 'Rollo', 2),
    ('MDT', 'JAL-0410.02', 'Aktor', 'Jalousieaktor 4 Kanäle', 'Rollo', 4),
    ('MDT', 'JAL-0810.02', 'Aktor', 'Jalousieaktor 8 Kanäle', 'Rollo', 8),
    ('MDT', 'AKD-0201.02', 'Aktor', 'Dimmaktor 2 Kanäle', 'Dimmen', 2),
    ('MDT', 'AKD-0401.02', 'Aktor', 'Dimmaktor 4 Kanäle', 'Dimmen', 4),
    ('MDT', 'AKD-0424R.02', 'Aktor', 'LED Controller 4 Kanäle', 'Dimmen', 4),
    ('MDT', 'AKD-0424R2.02', 'Aktor', 'LED Controller 4 Kanäle', 'Dimmen', 4),
    ('MDT', 'BE-TAL63T2.D1', 'Bedienelement', 'Taster Light 63 2-fach (I/O, Auf/Ab) mit Temperatursensor', '', None),
    ('MDT', 'SCN-BWM63.02', 'Sensor', 'Bewegungsmelder 63', '', None),
    ('MDT', 'SCN-BWM63T.02', 'Sensor', 'Bewegungsmelder 63 mit Temperatursensor', '', None),
    ('MDT', 'SCN-IP000.03', 'Systemgerät', 'IP Interface', '', None),
    ('Busch-Jaeger', '2CKA006132A0432', 'Sensor', 'Busch-Wächter PRO 280° KNX (Weiß)', '', None),
    ('Busch-Jaeger', '2CKA006132A0433', 'Sensor', 'Busch-Wächter PRO 280° KNX (Anthrazit/Schwarz)', '', None),
    ('Phoenix Contact', '1477019', 'Systemgerät', 'Busspannungsversorgung STEP3 640mA', '', None),
    ('Phoenix Contact', '1477020', 'Systemgerät', 'Busspannungsversorgung STEP3 1280mA', '', None),
    ('Elsner Elektronik', 'Windancer 2.0 GPS KNX SEC', 'Wetterstation', 'Wetterstation mit GPS', '', None),
    ('Elsner Elektronik', 'Windancer 2.0 KNX SEC', 'Wetterstation', 'Wetterstation', '', None),
    ('Theben', '1509201', 'Wetterstation', 'Wetterstation Meteodata 150/24V KNX', '', None),
    ('Theben', '1509204', 'Wetterstation', 'Wetterstation Meteodata 150/24V GPS KNX', '', None),
    ('Gira', '209600', 'Visualisierung/Logik', 'X1 Server', '', None),
    ('Gira', '208600', 'Systemgerät', 'S1 Fernzugriff-Modul', '', None),
    ('Theben', '1019610', 'Sensor', 'Bewegungsmelder theLuxa P300 KNX WH (Weiß)', '', None),
    ('Theben', '1019611', 'Sensor', 'Bewegungsmelder theLuxa P300 KNX BK (Schwarz)', '', None),
    ('Enertex', '1167-24', 'Systemgerät', 'LED PowerSupply 160-24', '', None),
    ('Hörmann', '4511630', 'Aktor', 'KNX Gateway Standard für Torantriebe', 'Tor', 1),
]


def seed_default_actor_types(db):
    """Seed the device catalog with a starter set of common KNX devices (MDT/Busch-Jaeger/
    Theben/Elsner/Gira/Phoenix Contact/Hörmann) so new installs aren't empty. Only runs
    once, when actor_types is empty - never overwrites a catalog the user has since edited."""
    db.executemany(
        "INSERT INTO actor_types (manufacturer, model, group_name, description, channel_type, channel_count) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        DEFAULT_ACTOR_TYPES,
    )
