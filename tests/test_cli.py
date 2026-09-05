"""CLI argv, --json placement, refusals, exit codes."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from fetch_media import EXIT_FAIL, EXIT_OK, SCHEMA
from fetch_media.cli import main
from fetch_media.errors import COOKIES_UNSUPPORTED
from fetch_media.result import failed, ok


class CliJsonFlagTests(unittest.TestCase):
    def test_json_before_subcommand(self) -> None:
        chip = ok("https://example.com/a.mp4", path="/tmp/fetch-media/a.mp4", title="A")
        with patch("fetch_media.cli.get_media", return_value=chip):
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--json", "get", "https://example.com/a.mp4"])
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["path"], "/tmp/fetch-media/a.mp4")

    def test_json_after_subcommand(self) -> None:
        chip = ok("https://example.com/a.mp4", path="/tmp/fetch-media/a.mp4")
        with patch("fetch_media.cli.get_media", return_value=chip):
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["get", "https://example.com/a.mp4", "--json"])
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(json.loads(out.getvalue())["status"], "OK")

    def test_failed_still_prints_json_exit_2(self) -> None:
        chip = failed("https://example.com/nope", "boom")
        with patch("fetch_media.cli.get_media", return_value=chip):
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--json", "get", "https://example.com/nope"])
        self.assertEqual(code, EXIT_FAIL)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "FAILED")
        self.assertIsNone(payload["path"])
        self.assertEqual(payload["error"], "boom")
        self.assertIsNone(payload["title"])

    def test_cookies_from_browser_refused(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(
                [
                    "--json",
                    "get",
                    "https://www.youtube.com/watch?v=dQw4w9wgGcQ",
                    "--cookies-from-browser",
                    "chrome",
                ]
            )
        self.assertEqual(code, EXIT_FAIL)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "FAILED")
        self.assertIsNone(payload["path"])
        self.assertIn("cookies-from-browser", payload["error"])
        self.assertEqual(payload["error"], COOKIES_UNSUPPORTED)

    def test_cookies_equals_form_refused(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--json", "get", "https://example.com/a.mp4", "--cookies=/tmp/cookies.txt"])
        self.assertEqual(code, EXIT_FAIL)
        self.assertIsNone(json.loads(out.getvalue())["path"])

    def test_human_mode_is_not_json(self) -> None:
        chip = ok("https://example.com/a.mp4", path="/tmp/fetch-media/a.mp4", title="A")
        with patch("fetch_media.cli.get_media", return_value=chip):
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["get", "https://example.com/a.mp4"])
        self.assertEqual(code, EXIT_OK)
        text = out.getvalue()
        self.assertTrue(text.startswith("OK"))
        self.assertNotIn('"schema"', text)

    def test_unknown_command_exits_nonzero(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["wat"])
        self.assertNotEqual(code, EXIT_OK)

    def test_exec_flag_failed_json_null_path(self) -> None:
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--json", "get", "--exec", "id", "https://example.com/a.mp4"])
        self.assertEqual(code, EXIT_FAIL)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "FAILED")
        self.assertIsNone(payload["path"])
        self.assertIn("unrecognized", payload["error"])

    def test_json_without_command(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--json"])
        self.assertEqual(code, EXIT_FAIL)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "FAILED")
        self.assertIsNone(payload["path"])

    def test_info_dispatches(self) -> None:
        chip = ok("https://example.com/a.mp4", title="A", extractor="generic")
        with patch("fetch_media.cli.info_media", return_value=chip) as info:
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--json", "info", "https://example.com/a.mp4"])
        self.assertEqual(code, EXIT_OK)
        info.assert_called_once()
        self.assertIsNone(json.loads(out.getvalue())["path"])


if __name__ == "__main__":
    unittest.main()
