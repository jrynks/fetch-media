"""get: mocked yt-dlp OK path, FAILED never invents a path, --audio-only argv."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fetch_media.ytdlp import build_get_argv, get_media


def _proc(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["yt-dlp"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class BuildGetArgvTests(unittest.TestCase):
    def test_ignore_config_is_always_passed(self) -> None:
        argv = build_get_argv("https://example.com/a", yt_dlp=["yt-dlp"])
        self.assertIn("--ignore-config", argv)

    def test_audio_only_adds_extract_flags(self) -> None:
        argv = build_get_argv(
            "https://example.com/a",
            audio_only=True,
            yt_dlp=["yt-dlp"],
        )
        self.assertIn("-x", argv)
        self.assertIn("--audio-format", argv)
        i = argv.index("--audio-format")
        self.assertEqual(argv[i + 1], "mp3")
        self.assertIn("--no-playlist", argv)
        self.assertIn("--restrict-filenames", argv)
        self.assertIn("--write-info-json", argv)

    def test_playlist_omits_no_playlist(self) -> None:
        argv = build_get_argv(
            "https://example.com/a",
            playlist=True,
            yt_dlp=["yt-dlp"],
        )
        self.assertNotIn("--no-playlist", argv)

    def test_format_and_max_filesize(self) -> None:
        argv = build_get_argv(
            "https://example.com/a",
            format="bestaudio/best",
            max_filesize="50M",
            yt_dlp=["yt-dlp"],
        )
        self.assertIn("-f", argv)
        self.assertEqual(argv[argv.index("-f") + 1], "bestaudio/best")
        self.assertEqual(argv[argv.index("--max-filesize") + 1], "50M")

    def test_url_after_double_dash(self) -> None:
        argv = build_get_argv("https://example.com/a", yt_dlp=["yt-dlp"])
        self.assertEqual(argv[-2], "--")
        self.assertEqual(argv[-1], "https://example.com/a")

    def test_invalid_format_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_get_argv("https://example.com/a", format="best; rm -rf /", yt_dlp=["yt-dlp"])

    def test_no_shell_metacharacters_as_single_argv(self) -> None:
        argv = build_get_argv("https://example.com/a && reboot", yt_dlp=["yt-dlp"])
        self.assertIn("https://example.com/a && reboot", argv)
        self.assertTrue(all(isinstance(x, str) for x in argv))


class GetMediaMockTests(unittest.TestCase):
    def test_ok_path_from_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "vid123.mp4"
            media.write_bytes(b"not-a-real-video")
            (Path(tmp) / "vid123.info.json").write_text(
                json.dumps(
                    {
                        "id": "vid123",
                        "title": "Hello World",
                        "ext": "mp4",
                        "duration": 19.4,
                        "extractor": "youtube",
                    }
                ),
                encoding="utf-8",
            )
            with patch("fetch_media.ytdlp.find_yt_dlp", return_value=["yt-dlp"]), patch(
                "fetch_media.ytdlp.run_subprocess",
                return_value=_proc(0, stdout=f"{media}\n"),
            ):
                result = get_media("https://www.youtube.com/watch?v=vid123", out_dir=tmp)
            self.assertEqual(result.status, "OK")
            self.assertEqual(result.path, str(media.resolve()))
            self.assertEqual(result.title, "Hello World")
            self.assertEqual(result.duration_sec, 19)
            self.assertEqual(result.extractor, "youtube")
            self.assertEqual(result.id, "vid123")
            self.assertEqual(result.ext, "mp4")
            self.assertIsNone(result.error)
            chip = result.to_dict()
            self.assertEqual(chip["path"], str(media.resolve()))
            self.assertEqual(chip["schema"], "fetch-media/v1")

    def test_failed_no_invented_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("fetch_media.ytdlp.find_yt_dlp", return_value=["yt-dlp"]), patch(
                "fetch_media.ytdlp.run_subprocess",
                return_value=_proc(1, stderr="ERROR: [youtube] Private video"),
            ):
                result = get_media("https://www.youtube.com/watch?v=private1", out_dir=tmp)
            self.assertEqual(result.status, "FAILED")
            self.assertIsNone(result.path)
            self.assertIsNone(result.title)
            self.assertIsNone(result.duration_sec)
            chip = result.to_dict()
            self.assertIsNone(chip["path"])
            self.assertIn("private", chip["error"].lower())
            self.assertNotIn("/tmp/fetch-media/private1", json.dumps(chip))

    def test_zero_exit_but_missing_file_is_failed_null_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            invented = str(Path(tmp) / "ghost.mp4")
            with patch("fetch_media.ytdlp.find_yt_dlp", return_value=["yt-dlp"]), patch(
                "fetch_media.ytdlp.run_subprocess",
                return_value=_proc(0, stdout=invented + "\n"),
            ):
                result = get_media("https://example.com/ghost.mp4", out_dir=tmp)
            self.assertEqual(result.status, "FAILED")
            self.assertIsNone(result.path)
            self.assertIsNone(result.to_dict()["path"])
            self.assertNotEqual(result.path, invented)

    def test_part_file_is_not_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            part = Path(tmp) / "vid.mp4.part"
            part.write_bytes(b"partial")
            with patch("fetch_media.ytdlp.find_yt_dlp", return_value=["yt-dlp"]), patch(
                "fetch_media.ytdlp.run_subprocess",
                return_value=_proc(0, stdout=f"{part}\n"),
            ):
                result = get_media("https://example.com/vid.mp4", out_dir=tmp)
            self.assertEqual(result.status, "FAILED")
            self.assertIsNone(result.path)

    def test_nonzero_exit_ignores_leftover_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            leftover = Path(tmp) / "half.mp4"
            leftover.write_bytes(b"half")
            with patch("fetch_media.ytdlp.find_yt_dlp", return_value=["yt-dlp"]), patch(
                "fetch_media.ytdlp.run_subprocess",
                return_value=_proc(1, stdout=f"{leftover}\n", stderr="ERROR: Download aborted"),
            ):
                result = get_media("https://example.com/half.mp4", out_dir=tmp)
            self.assertEqual(result.status, "FAILED")
            self.assertIsNone(result.path)
            self.assertIsNone(result.title)

    def test_file_url_refused(self) -> None:
        result = get_media("file:///etc/passwd")
        self.assertEqual(result.status, "FAILED")
        self.assertIsNone(result.path)
        self.assertIn("http(s)", result.error or "")

    def test_loopback_refused(self) -> None:
        result = get_media("http://127.0.0.1/secret.mp4")
        self.assertEqual(result.status, "FAILED")
        self.assertIsNone(result.path)

    def test_max_filesize_enforced_on_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "vid.mp4"
            media.write_bytes(b"x" * 5000)
            (Path(tmp) / "vid.info.json").write_text(
                json.dumps({"id": "vid", "title": "T", "ext": "mp4", "duration": 1}),
                encoding="utf-8",
            )
            with patch("fetch_media.ytdlp.find_yt_dlp", return_value=["yt-dlp"]), patch(
                "fetch_media.ytdlp.run_subprocess",
                return_value=_proc(0, stdout=f"{media}\n"),
            ):
                result = get_media(
                    "https://example.com/vid.mp4",
                    out_dir=tmp,
                    max_filesize="1K",
                )
            self.assertEqual(result.status, "FAILED")
            self.assertIsNone(result.path)
            self.assertIsNone(result.title)
            self.assertIn("max-filesize", result.error or "")

    def test_audio_ext_comes_from_file_not_info_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "vid123.mp3"
            media.write_bytes(b"id3")
            (Path(tmp) / "vid123.info.json").write_text(
                json.dumps(
                    {
                        "id": "vid123",
                        "title": "Song",
                        "ext": "mp4",
                        "duration": 8,
                        "extractor": "generic",
                    }
                ),
                encoding="utf-8",
            )
            with patch("fetch_media.ytdlp.find_yt_dlp", return_value=["yt-dlp"]), patch(
                "fetch_media.ytdlp.run_subprocess",
                return_value=_proc(0, stdout=f"{media}\n"),
            ):
                result = get_media(
                    "https://example.com/vid.mp4",
                    out_dir=tmp,
                    audio_only=True,
                )
            self.assertEqual(result.status, "OK")
            self.assertEqual(result.ext, "mp3")
            self.assertTrue(result.path and result.path.endswith(".mp3"))

    def test_timeout_failed_null_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("fetch_media.ytdlp.find_yt_dlp", return_value=["yt-dlp"]), patch(
                "fetch_media.ytdlp.run_subprocess",
                side_effect=subprocess.TimeoutExpired(cmd="yt-dlp", timeout=1),
            ):
                result = get_media("https://example.com/slow.mp4", out_dir=tmp, timeout=1)
            self.assertEqual(result.status, "FAILED")
            self.assertIsNone(result.path)
            self.assertIn("timed out", result.error or "")


if __name__ == "__main__":
    unittest.main()
