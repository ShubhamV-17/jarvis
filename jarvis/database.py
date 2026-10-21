"""SQLite initialization for local application state and tool auditing."""

import sqlite3
from contextlib import closing
from pathlib import Path


def initialize_database(database_file: Path) -> None:
    database_file.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(database_file)) as connection:
        with connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS app_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tool_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp_utc TEXT NOT NULL DEFAULT (
                        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                    ),
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    verification_outcome TEXT NOT NULL
                        CHECK (verification_outcome IN ('verified', 'failed', 'not_run'))
                );

                PRAGMA user_version = 1;
                """
            )
