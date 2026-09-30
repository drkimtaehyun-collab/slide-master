#!/usr/bin/env python3
"""
Chart Summary - Local Transcription

Transcribes a Korean clinic recording to text with faster-whisper on this
machine. Audio is never uploaded. Medical vocabulary from
references/vocabulary.txt is passed as the initial prompt to improve drug and
term recognition.

Usage:
    python3 scripts/transcribe.py <audio> [-o transcript.txt] [--model large-v3]

Examples:
    python3 scripts/transcribe.py clinic/inbox/재진/C12345.m4a -o /tmp/C12345.txt
    python3 scripts/transcribe.py visit.m4a --model medium --device cpu

Dependencies:
    faster-whisper (pip install -r .claude/skills/chart-summary/requirements.txt)
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path
from typing import Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from chart_common import REFERENCES_DIR, configure_utf8_stdio  # noqa: E402

DEFAULT_MODEL = "large-v3"
_MODEL_CACHE: dict[tuple[str, str, str], object] = {}


def _load_model(name: str, device: str, compute_type: str):
    key = (name, device, compute_type)
    if key not in _MODEL_CACHE:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Run: "
                "pip install -r .claude/skills/chart-summary/requirements.txt"
            ) from exc
        _MODEL_CACHE[key] = WhisperModel(name, device=device, compute_type=compute_type)
    return _MODEL_CACHE[key]


def _vocabulary_prompt() -> Optional[str]:
    path = REFERENCES_DIR / "vocabulary.txt"
    if not path.exists():
        return None
    words = " ".join(path.read_text(encoding="utf-8").split())
    return words or None


def transcribe(audio: Path, *, model: str = DEFAULT_MODEL, device: str = "auto",
               compute_type: str = "default") -> str:
    """Return the transcript as one line per segment, prefixed with [mm:ss]."""
    whisper = _load_model(model, device, compute_type)
    segments, _info = whisper.transcribe(
        str(audio),
        language="ko",
        initial_prompt=_vocabulary_prompt(),
        vad_filter=True,
        beam_size=5,
    )
    lines = []
    for seg in segments:
        minutes, seconds = divmod(int(seg.start), 60)
        text = seg.text.strip()
        if text:
            lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Transcribe a clinic recording locally (Korean).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("audio", help="audio file (m4a, mp3, wav, ...)")
    parser.add_argument("-o", "--output", help="transcript path (default: stdout)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Whisper model (default: {DEFAULT_MODEL})")
    parser.add_argument("--device", default="auto", help="auto | cpu | cuda")
    parser.add_argument("--compute-type", default="default", help="e.g. int8 on slow CPUs")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    audio = Path(args.audio)
    if not audio.is_file():
        print(f"Error: audio file not found: {audio}", file=sys.stderr)
        return 1
    try:
        text = transcribe(audio, model=args.model, device=args.device, compute_type=args.compute_type)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Transcript written: {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
