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
    for col in ("time_tracking_enabled", "time_tracking_rounding_minutes", "smtp_enabled", "dokumentation_include_handbuecher"):
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
    backend.db.init_db()
    backend.db.init_db()  # idempotent
    cp = columns(db_path, "company_profile")
    assert "zeiterfassung_enabled" not in cp and "time_tracking_enabled" in cp
    with sqlite3.connect(db_path) as c:
        assert c.execute("SELECT time_tracking_enabled, time_tracking_rounding_minutes FROM company_profile").fetchone() == (0, 30)
