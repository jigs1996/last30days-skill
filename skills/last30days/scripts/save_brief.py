#!/usr/bin/env python3
"""Archive a finished last30days brief that the host pipes in on stdin.

Fork replacement for the upstream Stop hook (capture_brief_hook.py): instead of
reading every session transcript after every turn, the skill pipes its own
finished report here once, at the end of a /last30days run. Reuses the same
detection, dedupe, and library-index logic, so saved files are identical.

Usage:
    "$LAST30DAYS_PYTHON" "$SKILL_DIR/scripts/save_brief.py" --save-dir "$SAVE_DIR" <<'EOF'
    <finished report: badge line through the fenced engine footer>
    EOF

An empty --save-dir means saving is disabled; nothing is written.
Always exits 0 so a failed archive never blocks presenting the report.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_MAX_STDIN_BYTES = 4 * 1024 * 1024
_DISABLED_VALUES = frozenset({"0", "false", "no", "off"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--save-dir", required=True, help="resolved save directory; empty disables saving")
    args = parser.parse_args()

    if os.environ.get("LAST30DAYS_AUTO_CAPTURE", "").strip().lower() in _DISABLED_VALUES:
        print("[last30days] brief archive skipped: LAST30DAYS_AUTO_CAPTURE is off")
        return 0
    if not args.save_dir.strip():
        print("[last30days] brief archive skipped: saving is disabled")
        return 0

    text = sys.stdin.read(_MAX_STDIN_BYTES + 1)
    if not text or len(text) > _MAX_STDIN_BYTES:
        print("[last30days] brief archive skipped: empty or oversized input")
        return 0

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from lib import brief_capture, library_index

        brief = brief_capture.extract_finished_brief(text)
        if brief is None:
            print("[last30days] brief archive skipped: no finished brief found (badge and fenced footer required)")
            return 0
        outcome = brief_capture.save_finished_brief(brief, args.save_dir)
        if outcome.status == "saved":
            save_root = Path(args.save_dir).expanduser().resolve()
            try:
                library_index.index_entry(
                    outcome.path,
                    db_path=library_index.saved_report_index_path(save_root),
                    source_format="finished-brief",
                )
            except Exception as exc:  # index is best-effort, the file is saved
                print(f"[last30days] brief saved; index skipped ({type(exc).__name__})")
        print(f"[last30days] brief {outcome.status}: {outcome.path}")
    except Exception as exc:
        print(f"[last30days] brief archive failed ({type(exc).__name__}: {exc})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
