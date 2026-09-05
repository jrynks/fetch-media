"""fetch-media CLI. --json may appear anywhere; cookies flags are refused."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from fetch_media import DEFAULT_OUT_DIR, EXIT_FAIL, EXIT_OK, SCHEMA, __version__
from fetch_media.doctor import format_doctor_human, run_doctor
from fetch_media.errors import COOKIES_UNSUPPORTED
from fetch_media.result import FetchResult, failed
from fetch_media.ytdlp import get_media, info_media

REFUSED_SESSION_FLAGS = (
    "--cookies-from-browser",
    "--cookies",
    "--netrc",
    "--username",
    "--password",
    "--video-password",
    "--ap-username",
    "--ap-password",
)

DESCRIPTION = (
    "Thin yt-dlp wrapper for public media URLs. "
    "Prints a compact JSON chip (schema fetch-media/v1) so agents can work from disk paths."
)


def main(argv: Optional[Sequence[str]] = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    refusal = _session_flag_refusal(raw)
    if refusal is not None:
        result = failed(None, refusal)
        json_mode = "--json" in raw
        _emit(result, json_mode=json_mode, doctor=False)
        return EXIT_FAIL

    cleaned, json_mode = _strip_json_flag(raw)
    parser = _build_parser()
    try:
        args, unknown = parser.parse_known_args(cleaned)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else EXIT_FAIL
        if json_mode and code not in (0,):
            _emit(
                failed(None, "invalid arguments — see fetch-media --help"),
                json_mode=True,
                doctor=False,
            )
            return EXIT_FAIL
        return code if code is not None else EXIT_FAIL

    if unknown:
        result = failed(None, "unrecognized arguments: " + " ".join(unknown))
        _emit(result, json_mode=json_mode, doctor=False)
        return EXIT_FAIL

    if not getattr(args, "command", None):
        if json_mode:
            _emit(
                failed(None, "missing command (get|info|doctor)"),
                json_mode=True,
                doctor=False,
            )
            return EXIT_FAIL
        parser.print_help(sys.stderr)
        return EXIT_FAIL

    if args.command == "doctor":
        result = run_doctor(out_dir=Path(args.out) if args.out else DEFAULT_OUT_DIR)
        _emit(result, json_mode=json_mode, doctor=True)
        return EXIT_OK if result.status == "OK" else EXIT_FAIL

    url = getattr(args, "url", None)
    if args.command == "get":
        result = get_media(
            url,
            audio_only=bool(args.audio_only),
            format=args.format,
            out_dir=Path(args.out) if args.out else DEFAULT_OUT_DIR,
            playlist=bool(args.playlist),
            max_filesize=args.max_filesize,
        )
        _emit(result, json_mode=json_mode, doctor=False)
        return EXIT_OK if result.status == "OK" else EXIT_FAIL

    if args.command == "info":
        result = info_media(url, playlist=bool(args.playlist))
        _emit(result, json_mode=json_mode, doctor=False)
        return EXIT_OK if result.status == "OK" else EXIT_FAIL

    parser.print_help(sys.stderr)
    return EXIT_FAIL


def _emit(result: FetchResult, *, json_mode: bool, doctor: bool) -> None:
    if json_mode:
        sys.stdout.write(result.to_json())
        sys.stdout.write("\n")
        return
    if doctor:
        sys.stdout.write(format_doctor_human(result))
        sys.stdout.write("\n")
        return
    sys.stdout.write(result.format_human())
    sys.stdout.write("\n")


def _strip_json_flag(argv: Sequence[str]) -> tuple[list[str], bool]:
    json_mode = False
    cleaned: list[str] = []
    for arg in argv:
        if arg == "--json":
            json_mode = True
            continue
        cleaned.append(arg)
    return cleaned, json_mode


def _session_flag_refusal(argv: Sequence[str]) -> Optional[str]:
    for arg in argv:
        name = arg.split("=", 1)[0]
        if name in REFUSED_SESSION_FLAGS:
            return COOKIES_UNSUPPORTED
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetch-media",
        description=DESCRIPTION,
        epilog=(
            f"schema {SCHEMA}  |  exit 0 = OK, exit 2 = FAILED  |  "
            "public http(s) URLs only"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command")

    get_p = sub.add_parser(
        "get",
        help="Download public media and print a path chip",
    )
    get_p.add_argument("url", help="Public http(s) media URL")
    get_p.add_argument(
        "--audio-only",
        action="store_true",
        help="Extract audio (-x --audio-format mp3)",
    )
    get_p.add_argument(
        "--format",
        metavar="FORMAT",
        help="yt-dlp -f format selector",
    )
    get_p.add_argument(
        "--out",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUT_DIR})",
    )
    get_p.add_argument(
        "--playlist",
        action="store_true",
        help="Allow playlists (default: --no-playlist)",
    )
    get_p.add_argument(
        "--max-filesize",
        metavar="SIZE",
        help="Abort if the file is larger than SIZE (e.g. 50M)",
    )
    # Present so the flag is recognized, then refused in main().
    get_p.add_argument("--cookies-from-browser", nargs="?", const="denied", help=argparse.SUPPRESS)
    get_p.add_argument("--cookies", help=argparse.SUPPRESS)

    info_p = sub.add_parser(
        "info",
        help="Metadata only — no download",
    )
    info_p.add_argument("url", help="Public http(s) media URL")
    info_p.add_argument(
        "--playlist",
        action="store_true",
        help="Allow playlists (default: dump single entry)",
    )
    info_p.add_argument("--cookies-from-browser", nargs="?", const="denied", help=argparse.SUPPRESS)
    info_p.add_argument("--cookies", help=argparse.SUPPRESS)

    doctor_p = sub.add_parser("doctor", help="Check yt-dlp, ffmpeg, and out dir")
    doctor_p.add_argument(
        "--out",
        default=DEFAULT_OUT_DIR,
        help=f"Output directory to probe (default: {DEFAULT_OUT_DIR})",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
