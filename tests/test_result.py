"""FAILED chips never carry a path; metadata is not invented."""

from __future__ import annotations

import json
import unittest

from fetch_media.result import duration_sec_from, failed, ok


class ResultContractTests(unittest.TestCase):
    def test_failed_forces_path_none_even_if_set(self) -> None:
        chip = failed("https://example.com/a", "nope")
        chip.path = "/tmp/fetch-media/fake.mp4"  # attacker/mistake
        payload = chip.to_dict()
        self.assertIsNone(payload["path"])
        self.assertEqual(payload["status"], "FAILED")
        self.assertNotIn("fake.mp4", json.dumps(payload))

    def test_ok_keeps_real_path(self) -> None:
        chip = ok("https://example.com/a", path="/tmp/fetch-media/a.mp4", title="A")
        self.assertEqual(chip.to_dict()["path"], "/tmp/fetch-media/a.mp4")

    def test_duration_not_guessed(self) -> None:
        self.assertIsNone(duration_sec_from(None))
        self.assertIsNone(duration_sec_from("nope"))
        self.assertIsNone(duration_sec_from(float("nan")))
        self.assertIsNone(duration_sec_from(-4))
        self.assertEqual(duration_sec_from(19.4), 19)
        self.assertEqual(duration_sec_from("12"), 12)

    def test_compact_json(self) -> None:
        text = failed("https://example.com/a", "x").to_json()
        self.assertNotIn(" ", text)
        self.assertIn('"schema":"fetch-media/v1"', text)


if __name__ == "__main__":
    unittest.main()
