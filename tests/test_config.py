import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jarvis.config import load_settings


class LoadSettingsTests(unittest.TestCase):
    def test_loads_defaults_and_resolves_data_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch.dict(os.environ, {}, clear=True):
                settings = load_settings(root)

        self.assertEqual(settings.project_root, root.resolve())
        self.assertEqual(settings.data_dir, (root / "data").resolve())
        self.assertEqual(settings.log_level, "INFO")
        self.assertEqual(settings.model, "gpt-5-mini")
        self.assertIsNone(settings.openai_api_key)

    def test_rejects_invalid_log_level(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.dict(os.environ, {"JARVIS_LOG_LEVEL": "VERBOSE"}, clear=True):
                with self.assertRaisesRegex(ValueError, "Unsupported JARVIS_LOG_LEVEL"):
                    load_settings(Path(temporary_directory))

    def test_api_key_is_not_in_settings_repr(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.dict(
                os.environ,
                {"OPENAI_API_KEY": "test-secret-value"},
                clear=True,
            ):
                settings = load_settings(Path(temporary_directory))

        self.assertNotIn("test-secret-value", repr(settings))
