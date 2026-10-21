import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from jarvis.database import initialize_database


class InitializeDatabaseTests(unittest.TestCase):
    def test_creates_database_and_audit_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_file = Path(temporary_directory) / "data" / "jarvis.sqlite3"
            initialize_database(database_file)

            with closing(sqlite3.connect(database_file)) as connection:
                table_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                user_version = connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertIn("app_metadata", table_names)
        self.assertIn("tool_audit_log", table_names)
        self.assertEqual(user_version, 1)

    def test_audit_log_rejects_unknown_verification_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_file = Path(temporary_directory) / "jarvis.sqlite3"
            initialize_database(database_file)

            with closing(sqlite3.connect(database_file)) as connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO tool_audit_log (
                            tool_name,
                            arguments_json,
                            result_json,
                            verification_outcome
                        ) VALUES ('example', '{}', '{}', 'unknown')
                        """
                    )


if __name__ == "__main__":
    unittest.main()
