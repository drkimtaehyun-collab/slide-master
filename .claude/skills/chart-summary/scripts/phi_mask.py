#!/usr/bin/env python3
"""
Chart Summary - Identifier Masking

Masks structured Korean identifiers (resident registration numbers, phone
numbers, emails, card/account-like digit runs) in a transcript before it is
sent off-machine. Names and free-text addresses are NOT reliably caught, so
this is risk reduction, not de-identification.

Usage:
    python3 scripts/phi_mask.py <transcript.txt> [-o masked.txt]

Examples:
    python3 scripts/phi_mask.py clinic/work/C12345.txt

Dependencies:
    None (only uses standard library)
"""
from __future__ import annotations

import re
import sys
import argparse
from pathlib import Path
from typing import Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from chart_common import configure_utf8_stdio  # noqa: E402

# Digit lookarounds instead of \b: Korean particles glue onto numbers ("010-...-5678로"),
# and Hangul counts as \w, so \b would never match there.
# Order matters: the RRN pattern must run before the generic long-digit pattern.
_MASKS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<!\d)\d{6}\s*-\s*[1-8]\d{6}(?!\d)"), "[주민번호]"),
    (re.compile(r"(?<!\d)01[016789][\s.-]?\d{3,4}[\s.-]?\d{4}(?!\d)"), "[전화번호]"),
    (re.compile(r"(?<!\d)0\d{1,2}[\s.-]\d{3,4}[\s.-]\d{4}(?!\d)"), "[전화번호]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+"), "[이메일]"),
    (re.compile(r"(?<!\d)\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{3,4}(?!\d)"), "[카드번호]"),
    (re.compile(r"(?<!\d)\d{10,16}(?!\d)"), "[번호]"),
]


def mask_identifiers(text: str) -> str:
    for pattern, label in _MASKS:
        text = pattern.sub(label, text)
    return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mask structured identifiers in a transcript.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("transcript", help="UTF-8 transcript file")
    parser.add_argument("-o", "--output", help="write masked text here (default: stdout)")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args(argv)
    masked = mask_identifiers(Path(args.transcript).read_text(encoding="utf-8"))
    if args.output:
        Path(args.output).write_text(masked, encoding="utf-8")
    else:
        sys.stdout.write(masked)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
