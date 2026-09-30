#!/usr/bin/env python3
"""
Chart Summary - Inbox Watcher

Watches the clinic workspace inbox and turns every finished recording (or
.txt transcript) into a chart draft:

    inbox/초진/<file>  -> 초진 format
    inbox/재진/<file>  -> 재진 format
    inbox/<file>       -> Claude decides (auto)

Audio is transcribed locally, identifiers are masked, the summary is written
to charts/YYYY-MM-DD/, and the source is moved to archive/ (or deleted with
--delete-audio). Failures go to failed/ with an .error.txt next to them.
Logs carry file names only, never transcript content.

Usage:
    python3 scripts/watch_inbox.py [--once] [--interval 10] [--delete-audio] [--purge-days N]

Examples:
    python3 scripts/watch_inbox.py                   # watch until Ctrl+C
    python3 scripts/watch_inbox.py --once            # process what is there now, then exit
    python3 scripts/watch_inbox.py --purge-days 7    # also delete archived audio/transcripts after 7 days

Dependencies:
    faster-whisper (audio only), Claude Code CLI (`claude`)
"""
from __future__ import annotations

import sys
import time
import shutil
import argparse
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from chart_common import (  # noqa: E402
    AUDIO_EXTS,
    TEXT_EXTS,
    VISIT_AUTO,
    VISIT_FOLLOWUP,
    VISIT_INITIAL,
    configure_utf8_stdio,
    workspace_dir,
)
from summarize import summarize_text  # noqa: E402

try:
    import faster_whisper  # noqa: F401
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

SETTLE_SEC = 5  # a file must be unchanged this long before we treat the copy as finished
_IGNORED_SUFFIXES = {".part", ".crdownload", ".tmp", ".download"}


class Workspace:
    def __init__(self, root: Path):
        self.root = root
        self.inbox = root / "inbox"
        self.work = root / "work"
        self.charts = root / "charts"
        self.archive = root / "archive"
        self.failed = root / "failed"

    def ensure(self) -> None:
        for path in (self.inbox / VISIT_INITIAL, self.inbox / VISIT_FOLLOWUP,
                     self.work, self.charts, self.archive, self.failed):
            path.mkdir(parents=True, exist_ok=True)


def _log(message: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {message}", file=sys.stderr, flush=True)


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    for n in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_{n}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"too many files named like {path.name}")


def _candidates(ws: Workspace) -> list[tuple[Path, str]]:
    found = []
    for folder, visit in ((ws.inbox, VISIT_AUTO),
                          (ws.inbox / VISIT_INITIAL, VISIT_INITIAL),
                          (ws.inbox / VISIT_FOLLOWUP, VISIT_FOLLOWUP)):
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.name.startswith((".", "~")):
                continue
            suffix = path.suffix.lower()
            if suffix in _IGNORED_SUFFIXES or suffix not in AUDIO_EXTS | TEXT_EXTS:
                continue
            if suffix in AUDIO_EXTS and not HAS_WHISPER:
                continue  # left in the inbox until faster-whisper is installed
            found.append((path, visit))
    return found


def _is_settled(path: Path, sizes: dict[Path, int]) -> bool:
    stat = path.stat()
    previous = sizes.get(path)
    sizes[path] = stat.st_size
    return previous == stat.st_size and time.time() - stat.st_mtime >= SETTLE_SEC


def process_file(path: Path, visit: str, ws: Workspace, args: argparse.Namespace) -> None:
    day = date.today().isoformat()
    if path.suffix.lower() in TEXT_EXTS:
        transcript = path.read_text(encoding="utf-8")
    else:
        from transcribe import transcribe  # lazy: faster-whisper is heavy and optional for .txt input
        _log(f"전사 중: {path.name}")
        transcript = transcribe(path, model=args.model, device=args.device, compute_type=args.compute_type)
        work_dir = ws.work / day
        work_dir.mkdir(parents=True, exist_ok=True)
        _unique(work_dir / f"{path.stem}.txt").write_text(transcript, encoding="utf-8")

    if not transcript.strip():
        raise RuntimeError("transcript is empty (silent or unreadable recording)")

    _log(f"요약 중: {path.name} ({visit})")
    resolved, chart = summarize_text(transcript, visit, model=args.claude_model)
    chart_dir = ws.charts / day
    chart_dir.mkdir(parents=True, exist_ok=True)
    out = _unique(chart_dir / f"{path.stem}_{resolved}.md")
    out.write_text(chart, encoding="utf-8")

    if args.delete_audio:
        path.unlink()
    else:
        archive_dir = ws.archive / day
        archive_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(_unique(archive_dir / path.name)))
    _log(f"완료: {out.relative_to(ws.root)}")


def _fail(path: Path, ws: Workspace, error: BaseException) -> None:
    target = _unique(ws.failed / path.name)
    shutil.move(str(path), str(target))
    target.with_name(target.name + ".error.txt").write_text(f"{type(error).__name__}: {error}\n", encoding="utf-8")
    _log(f"실패: {path.name} -> failed/ ({type(error).__name__})")


def purge_old(ws: Workspace, days: int) -> None:
    cutoff = time.time() - days * 86400
    for base in (ws.archive, ws.work):
        for path in base.rglob("*"):
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                _log(f"보관기간 경과 삭제: {path.relative_to(ws.root)}")
        for folder in sorted((p for p in base.rglob("*") if p.is_dir()), reverse=True):
            if not any(folder.iterdir()):
                folder.rmdir()


def run_once(ws: Workspace, args: argparse.Namespace, sizes: dict[Path, int], *, wait_settle: bool) -> int:
    processed = 0
    for path, visit in _candidates(ws):
        if wait_settle and not _is_settled(path, sizes):
            continue
        sizes.pop(path, None)
        try:
            process_file(path, visit, ws, args)
            processed += 1
        except (RuntimeError, OSError, UnicodeDecodeError, subprocess.TimeoutExpired) as exc:
            _fail(path, ws, exc)
    if args.purge_days:
        purge_old(ws, args.purge_days)
    return processed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Watch the clinic inbox and auto-generate chart drafts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--once", action="store_true", help="process current inbox files and exit")
    parser.add_argument("--interval", type=int, default=10, help="poll interval in seconds (default: 10)")
    parser.add_argument("--delete-audio", action="store_true",
                        help="delete the source file after a successful summary instead of archiving it")
    parser.add_argument("--purge-days", type=int, default=0,
                        help="delete archive/ and work/ files older than N days (0 = keep)")
    parser.add_argument("--model", default="large-v3", help="Whisper model (default: large-v3)")
    parser.add_argument("--device", default="auto", help="Whisper device: auto | cpu | cuda")
    parser.add_argument("--compute-type", default="default", help="Whisper compute type, e.g. int8")
    parser.add_argument("--claude-model", help="Claude model override for summaries")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    if args.interval < 1 or args.purge_days < 0:
        print("Error: --interval must be >= 1 and --purge-days >= 0", file=sys.stderr)
        return 2
    ws = Workspace(workspace_dir())
    ws.ensure()
    if not HAS_WHISPER:
        _log("경고: faster-whisper 미설치 — 녹음 파일은 inbox에 그대로 두고 .txt만 처리합니다. "
             "pip install -r .claude/skills/chart-summary/requirements.txt")
    sizes: dict[Path, int] = {}

    if args.once:
        count = run_once(ws, args, sizes, wait_settle=False)
        _log(f"처리 {count}건")
        return 0

    _log(f"감시 시작: {ws.inbox} (Ctrl+C로 종료)")
    try:
        while True:
            run_once(ws, args, sizes, wait_settle=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        _log("감시 종료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
