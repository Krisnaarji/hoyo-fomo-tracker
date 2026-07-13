"""app.settings tests. IMPORTANT: every test patches app.settings.ENV_PATH
to a temp file with fake, test-only content this test writes itself - the
real .env is never opened or read. Tests also never snapshot or copy the
process environment (os.environ) as a whole - only uniquely-generated
HOYO_TEST_* keys are touched and individually removed in tearDown, so no
real secret is ever read, copied, or displayed by this file."""
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from app import settings


class LoadEnvFileTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._owned_keys = []

    def tearDown(self):
        for key in self._owned_keys:
            os.environ.pop(key, None)
        self._tmp_dir.cleanup()

    def _new_key(self) -> str:
        key = f"HOYO_TEST_{uuid.uuid4().hex}"
        self._owned_keys.append(key)
        return key

    def _fake_env_path(self, content: str) -> Path:
        path = Path(self._tmp_dir.name) / "fake.env"
        path.write_text(content)
        return path

    def test_missing_env_file_is_a_silent_noop(self):
        missing_path = Path(self._tmp_dir.name) / "does_not_exist.env"
        key = self._new_key()

        with patch.object(settings, "ENV_PATH", missing_path):
            settings.load_env_file()  # should not raise

        self.assertNotIn(key, os.environ)

    def test_simple_key_value_is_loaded(self):
        key = self._new_key()
        path = self._fake_env_path(f"{key}=hello\n")

        with patch.object(settings, "ENV_PATH", path):
            settings.load_env_file()

        self.assertEqual(os.environ.get(key), "hello")

    def test_blank_lines_and_comments_are_ignored(self):
        key = self._new_key()
        ignored_key = self._new_key()
        path = self._fake_env_path(
            "\n"
            "# this is a comment\n"
            f"{key}=value1\n"
            "   \n"
            f"# {ignored_key}=should_not_load\n"
        )

        with patch.object(settings, "ENV_PATH", path):
            settings.load_env_file()

        self.assertEqual(os.environ.get(key), "value1")
        self.assertNotIn(ignored_key, os.environ)

    def test_surrounding_quotes_are_stripped(self):
        double_key = self._new_key()
        single_key = self._new_key()
        path = self._fake_env_path(
            f'{double_key}="quoted value"\n'
            f"{single_key}='single quoted'\n"
        )

        with patch.object(settings, "ENV_PATH", path):
            settings.load_env_file()

        self.assertEqual(os.environ.get(double_key), "quoted value")
        self.assertEqual(os.environ.get(single_key), "single quoted")

    def test_existing_environment_variable_takes_precedence(self):
        key = self._new_key()
        os.environ[key] = "already_set"
        path = self._fake_env_path(f"{key}=from_file\n")

        with patch.object(settings, "ENV_PATH", path):
            settings.load_env_file()

        # setdefault() must never override a value the process already has -
        # this is what protects a real secret from being clobbered by a
        # stray .env value.
        self.assertEqual(os.environ.get(key), "already_set")

    def test_line_without_equals_sign_is_ignored(self):
        key = self._new_key()
        path = self._fake_env_path(f"NOT_A_VALID_LINE_AT_ALL\n{key}=ok\n")

        with patch.object(settings, "ENV_PATH", path):
            settings.load_env_file()

        self.assertEqual(os.environ.get(key), "ok")

    def test_get_env_returns_default_when_key_missing(self):
        missing_path = Path(self._tmp_dir.name) / "does_not_exist.env"
        key = self._new_key()

        with patch.object(settings, "ENV_PATH", missing_path):
            result = settings.get_env(key, "fallback")

        self.assertEqual(result, "fallback")

    def test_get_env_returns_none_default_when_key_missing_and_no_default(self):
        missing_path = Path(self._tmp_dir.name) / "does_not_exist.env"
        key = self._new_key()

        with patch.object(settings, "ENV_PATH", missing_path):
            result = settings.get_env(key)

        self.assertIsNone(result)

    def test_get_env_loads_file_then_returns_value(self):
        key = self._new_key()
        path = self._fake_env_path(f"{key}=from_get_env\n")

        with patch.object(settings, "ENV_PATH", path):
            result = settings.get_env(key)

        self.assertEqual(result, "from_get_env")


if __name__ == "__main__":
    unittest.main()
