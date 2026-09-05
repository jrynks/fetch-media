# fetch-media

Local Linux CLI for agents **Clipper** and **Media**. Thin `yt-dlp` wrapper for
**public** http(s) URLs. One process, one compact JSON chip with a disk path —
no browser download loops, no pasting video into chat.

```bash
pip install -e .
fetch-media doctor
fetch-media --json get 'https://www.youtube.com/watch?v=…'
fetch-media --json info 'https://…'
```

## Contract

| | |
|---|---|
| Schema | `fetch-media/v1` |
| Output dir | `/tmp/fetch-media/` (override with `--out`) |
| Exit | `0` = OK, `2` = FAILED |
| FAILED chip | `path` is always `null` — never invented |
| Cookies | **not supported** (`--cookies-from-browser` is refused) |

```json
{
  "schema": "fetch-media/v1",
  "url": "https://example.com/watch?v=abc",
  "status": "OK",
  "path": "/tmp/fetch-media/abc.mp4",
  "title": "Example",
  "duration_sec": 19,
  "extractor": "youtube",
  "error": null,
  "id": "abc",
  "ext": "mp4"
}
```

`--json` may appear before or after the subcommand. With `--json`, stdout is
**only** that chip (one line). Human mode is for terminals, not agents.

On failure the chip is still written (`status: "FAILED"`, `path: null`). Titles,
durations, and filenames are never invented.

## Commands

### `fetch-media get URL [--audio-only] [--format FORMAT] [--out DIR] [--playlist] [--max-filesize SIZE] [--json]`

Invokes yt-dlp with safe defaults:

- `--no-playlist` unless `--playlist`
- `--restrict-filenames`
- `--write-info-json`
- `--audio-only` → `-x --audio-format mp3`

The file is written under `/tmp/fetch-media/` (or `--out`). The chip’s `path` is
the real on-disk file after `after_move`. If yt-dlp exits non-zero, times out, or
leaves only a `.part` fragment, the chip is FAILED with `path: null`.

### `fetch-media info URL [--json] [--playlist]`

`yt-dlp --dump-json --skip-download` — metadata only. `path` is always `null`.

### `fetch-media doctor [--json]`

Is `yt-dlp` on PATH? Version? Is `ffmpeg` available for merges? Is the out dir
writable?

## Non-goals (v1)

- No DRM circumvention beyond stock yt-dlp public streams
- No uploading
- No browser cookie-jar harvesting
- No private / login-only / members-only flows — use a public URL
- No `file://` or loopback URLs

## Install

Python 3.10+ (3.11+ preferred), plus system `ffmpeg` for merges.

```bash
pip install -e .          # pulls yt-dlp
fetch-media doctor
python -m unittest discover -s tests -v
```

`FETCH_MEDIA_YT_DLP` overrides the yt-dlp binary (used in tests).

## Agent usage

```bash
chip=$(fetch-media --json get "$URL")
path=$(python -c 'import json,sys; print(json.load(sys.stdin)["path"] or "")' <<<"$chip")
# work from $path — do not re-download
```
