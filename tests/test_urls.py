from __future__ import annotations

import unittest

from fetch_media.urls import UrlError, validate_public_url


class UrlTests(unittest.TestCase):
    def test_https_ok(self) -> None:
        self.assertEqual(
            validate_public_url("  https://www.youtube.com/watch?v=abc  "),
            "https://www.youtube.com/watch?v=abc",
        )

    def test_rejects_file(self) -> None:
        with self.assertRaises(UrlError):
            validate_public_url("file:///etc/passwd")

    def test_rejects_missing_scheme(self) -> None:
        with self.assertRaises(UrlError):
            validate_public_url("youtube.com/watch?v=abc")

    def test_rejects_empty(self) -> None:
        with self.assertRaises(UrlError):
            validate_public_url("   ")

    def test_rejects_javascript(self) -> None:
        with self.assertRaises(UrlError):
            validate_public_url("javascript:alert(1)")


if __name__ == "__main__":
    unittest.main()
