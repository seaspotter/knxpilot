"""Schema setup must work on a brand-new database AND upgrade old ones -
the fresh-install path broke once (actor_types.manual_url lost in the
one-time table rebuild), so both are covered here."""
import sqlite3

import backend.db


def columns(path, table):
    with sqlite3.connect(path) as c:
        return [r[1] for r in c.execute(f"PRAGMA table_info({table})")]


def test_fresh_install_has_all_columns(db_path):
    backend.db.init_db()
    assert "manual_url" in columns(db_path, "actor_types")
    assert "group_name" in columns(db_path, "actor_types")
    assert "invoiced" in columns(db_path, "time_entries")
    cp = columns(db_path, "company_profile")
    for col in ("time_tracking_enabled", "time_tracking_rounding_minutes", "smtp_enabled", "documentation_include_manuals"):
        assert col in cp
    with sqlite3.connect(db_path) as c:
        assert c.execute("SELECT COUNT(*) FROM actor_types").fetchone()[0] > 50  # starter catalog seeded
        assert c.execute("SELECT COUNT(*) FROM categories").fetchone()[0] > 0


def test_init_is_idempotent(db_path):
    backend.db.init_db()
    backend.db.init_db()
    assert "manual_url" in columns(db_path, "actor_types")


def test_upgrades_pre_group_name_actor_types(db_path):
    """An old install: actor_types still with the legacy "name" column and
    no group_name - must be rebuilt keeping ids, and end up with every newer
    column too."""
    with sqlite3.connect(db_path) as c:
        c.execute(
            "CREATE TABLE actor_types (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL DEFAULT '', "
            "manufacturer TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '', "
            "channel_type TEXT NOT NULL, channel_count INTEGER NOT NULL)"
        )
        c.execute("INSERT INTO actor_types (id, name, channel_type, channel_count) VALUES (42, 'AKS-0816.03', 'Schalten', 8)")
    backend.db.init_db()
    cols = columns(db_path, "actor_types")
    assert "name" not in cols and "group_name" in cols and "manual_url" in cols
    with sqlite3.connect(db_path) as c:
        assert c.execute("SELECT model, channel_count FROM actor_types WHERE id=42").fetchone() == ("AKS-0816.03", 8)


def test_upgrades_time_entries_without_invoiced(db_path):
    with sqlite3.connect(db_path) as c:
        c.execute(
            "CREATE TABLE time_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER, "
            "project_name TEXT NOT NULL DEFAULT '', started_at TEXT NOT NULL, ended_at TEXT, note TEXT NOT NULL DEFAULT '')"
        )
        c.execute("INSERT INTO time_entries (project_id, started_at, ended_at) VALUES (1, '2026-09-26T10:00:00+00:00', '2026-09-26T11:00:00+00:00')")
    backend.db.init_db()
    with sqlite3.connect(db_path) as c:
        assert c.execute("SELECT invoiced FROM time_entries").fetchone() == (0,)


def test_renames_german_company_profile_columns(db_path):
    """Columns renamed to English keep their values on an existing install."""
    backend.db.init_db()
    with sqlite3.connect(db_path) as c:
        c.execute("ALTER TABLE company_profile RENAME COLUMN time_tracking_enabled TO zeiterfassung_enabled")
        c.execute("ALTER TABLE company_profile RENAME COLUMN time_tracking_rounding_minutes TO zeiterfassung_rounding_minutes")
        c.execute("UPDATE company_profile SET zeiterfassung_enabled=0, zeiterfassung_rounding_minutes=30")
        c.execute("ALTER TABLE company_profile RENAME COLUMN specification_preamble TO pflichtenheft_preamble")
        c.execute("ALTER TABLE company_profile RENAME COLUMN documentation_include_circuit_list TO pflichtenheft_include_abgangsliste")
        c.execute("UPDATE company_profile SET pflichtenheft_preamble='Mein Text', pflichtenheft_include_abgangsliste=1")
    backend.db.init_db()
    backend.db.init_db()  # idempotent
    cp = columns(db_path, "company_profile")
    assert "zeiterfassung_enabled" not in cp and "time_tracking_enabled" in cp
    with sqlite3.connect(db_path) as c:
        assert c.execute("SELECT time_tracking_enabled, time_tracking_rounding_minutes FROM company_profile").fetchone() == (0, 30)
        assert c.execute("SELECT specification_preamble, documentation_include_circuit_list FROM company_profile").fetchone() == ("Mein Text", 1)
    assert not [col for col in cp if col.startswith(("pflichtenheft_", "dokumentation_", "zeiterfassung_"))]


def test_renames_klaerungen_table_to_clarifications(db_path):
    """The old German klaerungen table (with its typ/antwort columns) is
    renamed and keeps its rows and values on an existing install."""
    with sqlite3.connect(db_path) as c:
        c.execute(
            "CREATE TABLE klaerungen (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, "
            "room_id INTEGER, room_point_id INTEGER, text TEXT NOT NULL, typ TEXT NOT NULL DEFAULT 'Frage', "
            "status TEXT NOT NULL DEFAULT 'offen', antwort TEXT NOT NULL DEFAULT '', order_idx INTEGER NOT NULL DEFAULT 0, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        c.execute("INSERT INTO klaerungen (project_id, text, typ, antwort) VALUES (1, 'Spots dimmbar?', 'Frage', 'Ja')")
    backend.db.init_db()
    backend.db.init_db()  # idempotent
    tables = [r[0] for r in sqlite3.connect(db_path).execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert "klaerungen" not in tables and "clarifications" in tables
    cols = columns(db_path, "clarifications")
    assert "typ" not in cols and "antwort" not in cols and "type" in cols and "answer" in cols
    with sqlite3.connect(db_path) as c:
        assert c.execute("SELECT text, type, answer FROM clarifications").fetchone() == ("Spots dimmbar?", "Frage", "Ja")


def test_renames_verteiler_tables_to_distribution_boards(db_path):
    """The old German verteiler/verteiler_items tables are renamed and keep
    their rows and the verteiler_id foreign key (renamed too) on an existing
    install."""
    with sqlite3.connect(db_path) as c:
        c.execute(
            "CREATE TABLE verteiler (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id INTEGER NOT NULL, "
            "floor_id INTEGER, name TEXT NOT NULL DEFAULT '', row_count INTEGER NOT NULL DEFAULT 4, "
            "order_idx INTEGER NOT NULL DEFAULT 0)"
        )
        c.execute(
            "CREATE TABLE verteiler_items (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "verteiler_id INTEGER NOT NULL REFERENCES verteiler(id) ON DELETE CASCADE, row_idx INTEGER NOT NULL, "
            "position_idx INTEGER NOT NULL DEFAULT 0, item_type TEXT NOT NULL, label TEXT NOT NULL DEFAULT '', "
            "width_te INTEGER, actor_instance_id INTEGER)"
        )
        c.execute("CREATE UNIQUE INDEX idx_verteiler_items_actor_instance ON verteiler_items(actor_instance_id) WHERE actor_instance_id IS NOT NULL")
        c.execute("INSERT INTO verteiler (id, project_id, name, row_count) VALUES (1, 1, 'UV EG', 4)")
        c.execute("INSERT INTO verteiler_items (verteiler_id, row_idx, item_type, label) VALUES (1, 0, 'rcd', 'RCD 40A')")
    backend.db.init_db()
    backend.db.init_db()  # idempotent
    tables = [r[0] for r in sqlite3.connect(db_path).execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert "verteiler" not in tables and "distribution_boards" in tables
    assert "verteiler_items" not in tables and "distribution_board_items" in tables
    cols = columns(db_path, "distribution_board_items")
    assert "verteiler_id" not in cols and "distribution_board_id" in cols
    with sqlite3.connect(db_path) as c:
        assert c.execute("SELECT name, row_count FROM distribution_boards WHERE id=1").fetchone() == ("UV EG", 4)
        assert c.execute(
            "SELECT item_type, label FROM distribution_board_items WHERE distribution_board_id=1"
        ).fetchone() == ("rcd", "RCD 40A")
