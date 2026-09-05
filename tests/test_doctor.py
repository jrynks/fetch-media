"""doctor: reports yt-dlp / ffmpeg presence without inventing versions."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from fetch_media.cli import main
from fetch_media.doctor import run_doctor
from fetch_media.ytdlp import YtDlpNotFound


class DoctorTests(unittest.TestCase):
    def test_ok_when_yt_dlp_present(self) -> None:
        with patch("fetch_media.doctor.find_yt_dlp", return_value=["/usr/bin/yt-dlp"]), patch(
            "fetch_media.doctor._run_version", return_value="2025.09.01"
        ), patch(
            "fetch_media.doctor.find_ffmpeg", return_value="/usr/bin/ffmpeg"
        ), patch(
            "fetch_media.doctor._probe_ffmpeg",
            return_value={"ok": True, "version": "7.0.2", "path": "/usr/bin/ffmpeg"},
        ):
            result = run_doctor()
        self.assertEqual(result.status, "OK")
        extras = result.extras or {}
        self.assertTrue(extras["yt_dlp"]["ok"])
        self.assertEqual(extras["yt_dlp"]["version"], "2025.09.01")
        self.assertTrue(extras["ffmpeg"]["ok"])

    def test_failed_when_yt_dlp_missing(self) -> None:
        with patch("fetch_media.doctor.find_yt_dlp", side_effect=YtDlpNotFound("missing")):
            result = run_doctor()
        self.assertEqual(result.status, "FAILED")
        self.assertIsNone(result.path)
        extras = result.extras or {}
        self.assertFalse(extras["yt_dlp"]["ok"])
        self.assertIsNone(extras["yt_dlp"]["version"])

    def test_cli_json_doctor(self) -> None:
        with patch("fetch_media.cli.run_doctor") as runner:
            from fetch_media.result import ok

            runner.return_value = ok(
                None,
                extras={
                    "yt_dlp": {"ok": True, "version": "1", "path": "/bin/yt-dlp"},
                    "ffmpeg": {"ok": True, "version": "7", "path": "/bin/ffmpeg"},
                    "python": {"ok": True, "version": "3.11.2", "path": "/usr/bin/python3.11"},
                    "out_dir": {"path": "/tmp/fetch-media", "writable": True},
                },
            )
            out = io.StringIO()
            with redirect_stdout(out):
                code = main(["--json", "doctor"])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["status"], "OK")
        self.assertIsNone(payload["path"])
        self.assertEqual(payload["schema"], "fetch-media/v1")


if __name__ == "__main__":
    unittest.main()
