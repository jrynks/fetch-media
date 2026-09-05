"""info: metadata only, no path, no download flags."""

from __future__ import annotations

import json
import subprocess
import unittest
from unittest.mock import patch

from fetch_media.ytdlp import build_info_argv, info_media


def _proc(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["yt-dlp"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class InfoArgvTests(unittest.TestCase):
    def test_skip_download_and_dump_json(self) -> None:
        argv = build_info_argv("https://example.com/a", yt_dlp=["yt-dlp"])
        self.assertIn("--dump-json", argv)
        self.assertIn("--skip-download", argv)
        self.assertIn("--no-playlist", argv)
        self.assertIn("--ignore-config", argv)
        self.assertNotIn("-x", argv)


class InfoMediaTests(unittest.TestCase):
    def test_ok_metadata_path_null(self) -> None:
        payload = {
            "id": "abc",
            "title": "Clip",
            "ext": "mp4",
            "duration": 12,
            "extractor": "vimeo",
        }
        with patch("fetch_media.ytdlp.find_yt_dlp", return_value=["yt-dlp"]), patch(
            "fetch_media.ytdlp.run_subprocess",
            return_value=_proc(0, stdout=json.dumps(payload) + "\n"),
        ):
            result = info_media("https://vimeo.com/abc")
        self.assertEqual(result.status, "OK")
        self.assertIsNone(result.path)
        self.assertEqual(result.title, "Clip")
        self.assertEqual(result.duration_sec, 12)
        self.assertEqual(result.extractor, "vimeo")
        self.assertIsNone(result.to_dict()["path"])

    def test_failed_no_invented_metadata(self) -> None:
        with patch("fetch_media.ytdlp.find_yt_dlp", return_value=["yt-dlp"]), patch(
            "fetch_media.ytdlp.run_subprocess",
            return_value=_proc(1, stderr="ERROR: Sign in to confirm you’re not a bot"),
        ):
            result = info_media("https://www.youtube.com/watch?v=members")
        self.assertEqual(result.status, "FAILED")
        self.assertIsNone(result.path)
        self.assertIsNone(result.title)
        self.assertIsNone(result.duration_sec)
        self.assertIn("public URL", result.error or "")

    def test_malformed_json_failed(self) -> None:
        with patch("fetch_media.ytdlp.find_yt_dlp", return_value=["yt-dlp"]), patch(
            "fetch_media.ytdlp.run_subprocess",
            return_value=_proc(0, stdout="not json\n"),
        ):
            result = info_media("https://example.com/a")
        self.assertEqual(result.status, "FAILED")
        self.assertIsNone(result.path)
        self.assertIsNone(result.title)


if __name__ == "__main__":
    unittest.main()
