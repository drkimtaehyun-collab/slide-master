#!/usr/bin/env python3
"""
Chart Summary - Shared Helpers

Workspace paths, visit-type resolution, and console setup shared by the
chart-summary scripts. Not a CLI; import from sibling scripts.

Dependencies:
    None (only uses standard library)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
REFERENCES_DIR = SKILL_DIR / "references"
# scripts/chart_common.py: [0]=scripts [1]=chart-summary [2]=skills [3]=.claude [4]=repo
REPO_ROOT = Path(__file__).resolve().parents[4]

VISIT_INITIAL = "초진"
VISIT_FOLLOWUP = "재진"
VISIT_AUTO = "auto"
VISIT_ALIASES = {
    "초진": VISIT_INITIAL, "initial": VISIT_INITIAL, "new": VISIT_INITIAL,
    "재진": VISIT_FOLLOWUP, "followup": VISIT_FOLLOWUP, "follow-up": VISIT_FOLLOWUP,
    "auto": VISIT_AUTO,
}
FORMAT_FILES = {
    VISIT_INITIAL: REFERENCES_DIR / "format-initial.md",
    VISIT_FOLLOWUP: REFERENCES_DIR / "format-followup.md",
}

AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac", ".ogg", ".flac", ".webm", ".mp4", ".amr", ".3gp"}
TEXT_EXTS = {".txt"}


def workspace_dir() -> Path:
    """Patient-data workspace; override with CHART_WORKSPACE (keep it off cloud-sync folders)."""
    override = os.environ.get("CHART_WORKSPACE")
    return Path(override).expanduser().resolve() if override else REPO_ROOT / "clinic"


def normalize_visit(value: str) -> str:
    visit = VISIT_ALIASES.get(value.strip().lower())
    if visit is None:
        raise ValueError(f"unknown visit type: {value!r} (use 초진, 재진, or auto)")
    return visit


def configure_utf8_stdio() -> None:
    """Force UTF-8 console output so Korean status text never crashes on Windows code pages."""
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


if __name__ == "__main__":
    print("chart_common.py is a helper module; run watch_inbox.py, transcribe.py, or summarize.py.",
          file=sys.stderr)
    raise SystemExit(2)
