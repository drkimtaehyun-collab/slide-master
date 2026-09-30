#!/usr/bin/env python3
"""
Chart Summary - Transcript to Chart Draft

Masks identifiers in a transcript, then asks Claude Code in headless mode
(`claude -p`, all tools disabled) to write a chart draft in the clinic's
초진 or 재진 format from references/. With --visit auto, Claude picks the
visit type and the script reads it back from a marker line.

Usage:
    python3 scripts/summarize.py <transcript.txt> [--visit 초진|재진|auto] [-o chart.md]

Examples:
    python3 scripts/summarize.py clinic/work/C12345.txt --visit 재진
    python3 scripts/summarize.py visit.txt --visit auto -o clinic/charts/visit.md

Dependencies:
    Claude Code CLI (`claude`) logged in on this machine
"""
from __future__ import annotations

import os
import re
import sys
import shutil
import argparse
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from chart_common import (  # noqa: E402
    FORMAT_FILES,
    REFERENCES_DIR,
    VISIT_AUTO,
    VISIT_FOLLOWUP,
    VISIT_INITIAL,
    configure_utf8_stdio,
    normalize_visit,
)
from phi_mask import mask_identifiers  # noqa: E402

CLAUDE_TIMEOUT_SEC = 600
_VISIT_MARKER_RE = re.compile(r"^\s*<!--\s*visit:\s*(초진|재진)\s*-->\s*\n?")

SYSTEM_PROMPT = (
    "당신은 의원의 진료기록 작성 보조입니다. 진료 녹취록을 주어진 양식과 규칙에 따라 "
    "담당 의사가 검토할 차트 요약 초안으로 정리합니다. 녹취록에 없는 사실은 절대 만들지 않습니다. "
    "출력은 요청된 마크다운 본문만 작성합니다."
)


def build_prompt(transcript: str, visit: str) -> str:
    rules = (REFERENCES_DIR / "rules.md").read_text(encoding="utf-8")
    parts = [rules]
    if visit == VISIT_AUTO:
        for kind in (VISIT_INITIAL, VISIT_FOLLOWUP):
            parts.append(f"# [{kind} 양식]\n\n{FORMAT_FILES[kind].read_text(encoding='utf-8')}")
        parts.append(
            "# 진료 유형 판단\n\n녹취록을 보고 초진인지 재진인지 판단하세요 "
            "(이전 방문·기존 처방·검사 결과 확인 언급이 있으면 재진). "
            "출력 첫 줄에 `<!-- visit: 초진 -->` 또는 `<!-- visit: 재진 -->`를 쓰고, "
            "이어서 해당 양식으로 작성하세요. 판단이 애매하면 `확인 필요`에 그 이유를 적으세요."
        )
    else:
        parts.append(f"# [{visit} 양식]\n\n{FORMAT_FILES[visit].read_text(encoding='utf-8')}")
    parts.append(f"# 진료 녹취록\n\n<transcript>\n{transcript.strip()}\n</transcript>")
    parts.append("위 녹취록을 규칙과 양식에 따라 요약하세요.")
    return "\n\n---\n\n".join(parts)


def _claude_command(model: Optional[str]) -> list[str]:
    binary = os.environ.get("CHART_CLAUDE_BIN") or shutil.which("claude")
    if not binary:
        raise RuntimeError("Claude Code CLI (`claude`) not found on PATH; set CHART_CLAUDE_BIN.")
    cmd = [binary, "-p", "--tools", "", "--no-session-persistence", "--system-prompt", SYSTEM_PROMPT]
    if model:
        cmd += ["--model", model]
    return cmd


def summarize_text(transcript: str, visit: str, *, model: Optional[str] = None) -> tuple[str, str]:
    """Return (resolved visit type, chart markdown)."""
    prompt = build_prompt(mask_identifiers(transcript), visit)
    # Neutral cwd so repository CLAUDE.md files are not pulled into the context.
    with tempfile.TemporaryDirectory(prefix="chart-summary-") as cwd:
        result = subprocess.run(
            _claude_command(model),
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=cwd,
            timeout=CLAUDE_TIMEOUT_SEC,
        )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr.strip()[:500]}")
    chart = result.stdout.strip()
    if not chart:
        raise RuntimeError("claude -p returned an empty summary")

    resolved = visit
    marker = _VISIT_MARKER_RE.match(chart)
    if marker:
        resolved = marker.group(1)
        chart = chart[marker.end():].lstrip()
    elif visit == VISIT_AUTO:
        resolved = "미분류"
    return resolved, chart + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize a clinic transcript into a 초진/재진 chart draft.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("transcript", help="UTF-8 transcript file")
    parser.add_argument("--visit", default=VISIT_AUTO, help="초진 | 재진 | auto (default: auto)")
    parser.add_argument("-o", "--output", help="chart markdown path (default: stdout)")
    parser.add_argument("--model", help="Claude model override (default: Claude Code's default)")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    try:
        visit = normalize_visit(args.visit)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    path = Path(args.transcript)
    if not path.is_file():
        print(f"Error: transcript not found: {path}", file=sys.stderr)
        return 1
    try:
        resolved, chart = summarize_text(path.read_text(encoding="utf-8"), visit, model=args.model)
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.output:
        Path(args.output).write_text(chart, encoding="utf-8")
        print(f"[{resolved}] chart written: {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(chart)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
