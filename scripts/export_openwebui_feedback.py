#!/usr/bin/env python3
"""
Export Open WebUI evaluation feedback from webui.db to JSON.

Usage (from repo root, after copying DB out of Docker):
  docker cp millm-open-webui-1:/app/backend/data/webui.db ./webui.db
  python scripts/export_openwebui_feedback.py webui.db -o feedback-export.json

Or run inside the container (paths are container paths):
  docker cp scripts/export_openwebui_feedback.py millm-open-webui-1:/tmp/export_feedback.py
  docker exec millm-open-webui-1 python3 /tmp/export_feedback.py /app/backend/data/webui.db -o /tmp/feedback-export.json
  docker cp millm-open-webui-1:/tmp/feedback-export.json ./feedback-export.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path


def _json_default(obj: object) -> str:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


def main() -> int:
    p = argparse.ArgumentParser(description="Export Open WebUI feedback tables from webui.db to JSON.")
    p.add_argument(
        "db_path",
        type=Path,
        help="Path to webui.db (e.g. copied from container /app/backend/data/webui.db)",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("openwebui-feedback-export.json"),
        help="Output JSON file (default: openwebui-feedback-export.json)",
    )
    args = p.parse_args()

    if not args.db_path.is_file():
        print(f"Database not found: {args.db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(args.db_path))
    conn.row_factory = sqlite3.Row

    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]

    # Open WebUI uses "feedback" for ratings; include any similarly named tables across versions.
    export_tables = [
        t
        for t in tables
        if "feedback" in t.lower() or t.lower() in ("evaluation", "evaluations", "message_feedback")
    ]
    if not export_tables:
        # Fallback: dump table list so user can inspect
        print(
            "No known feedback table found. Tables in DB:\n  "
            + "\n  ".join(tables),
            file=sys.stderr,
        )
        return 2

    out: dict[str, object] = {"_meta": {"source_db": str(args.db_path.resolve()), "tables_exported": export_tables}}

    for name in export_tables:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{name}")').fetchall()]
        rows = conn.execute(f'SELECT * FROM "{name}"').fetchall()
        out[name] = [dict(zip(cols, row)) for row in rows]

    args.output.write_text(
        json.dumps(out, indent=2, default=_json_default, ensure_ascii=False),
        encoding="utf-8",
    )
    total = sum(len(out[t]) for t in export_tables if isinstance(out[t], list))
    print(f"Wrote {args.output} ({total} rows across {len(export_tables)} table(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
