"""Command-line interface for MEMORYBANK.

Subcommands: remember, recall, forget, list, stats. Every command emits JSON
(or a human table with --format table) and exits non-zero on failure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import TOOL_NAME, TOOL_VERSION
from .core import MemoryBank, MemoryBankError

_DEFAULT_PATH = os.environ.get("MEMORYBANK_PATH", "memorybank.jsonl")


def _emit(obj, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(obj, indent=2, sort_keys=True))
        return
    # table
    rows = obj if isinstance(obj, list) else [obj]
    if not rows:
        print("(no results)")
        return
    cols = ["id", "score", "importance", "tags", "text"]
    avail = [c for c in cols if c in rows[0]] or list(rows[0].keys())
    widths = {c: len(c) for c in avail}
    disp: list[dict] = []
    for r in rows:
        d = {}
        for c in avail:
            v = r.get(c, "")
            if isinstance(v, list):
                v = ",".join(str(x) for x in v)
            v = str(v)
            if c == "text" and len(v) > 60:
                v = v[:57] + "..."
            d[c] = v
            widths[c] = max(widths[c], len(v))
        disp.append(d)
    line = "  ".join(c.ljust(widths[c]) for c in avail)
    print(line)
    print("  ".join("-" * widths[c] for c in avail))
    for d in disp:
        print("  ".join(d[c].ljust(widths[c]) for c in avail))


def _build_parser() -> argparse.ArgumentParser:
    # Shared options available both globally and on every subcommand.
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--format", choices=["table", "json"], default="json")
    shared.add_argument("--path", default=_DEFAULT_PATH, help="path to the JSONL memory bank")

    p = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Portable agent memory store.",
        parents=[shared],
    )
    p.add_argument("--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")
    sub = p.add_subparsers(dest="cmd", required=True)

    rem = sub.add_parser("remember", help="store a new memory", parents=[shared])
    rem.add_argument("text")
    rem.add_argument("--tag", action="append", default=[], dest="tags")
    rem.add_argument("--importance", type=float, default=1.0)

    rec = sub.add_parser("recall", help="retrieve memories ranked by a query", parents=[shared])
    rec.add_argument("query")
    rec.add_argument("--limit", type=int, default=5)
    rec.add_argument("--tag", default=None)
    rec.add_argument("--no-touch", action="store_true", help="do not update recency")

    fgt = sub.add_parser("forget", help="delete a memory by id", parents=[shared])
    fgt.add_argument("id")

    sub.add_parser("list", help="list every memory", parents=[shared])
    sub.add_parser("stats", help="show bank statistics", parents=[shared])
    return p


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        bank = MemoryBank(args.path)
        if args.cmd == "remember":
            m = bank.add(args.text, tags=args.tags, importance=args.importance)
            _emit(m.to_dict(), args.format)
        elif args.cmd == "recall":
            results = bank.search(
                args.query, limit=args.limit, tag=args.tag, touch=not args.no_touch
            )
            _emit(results, args.format)
        elif args.cmd == "forget":
            m = bank.forget(args.id)
            _emit({"forgotten": m.id, "text": m.text}, args.format)
        elif args.cmd == "list":
            _emit([m.to_dict() for m in bank.all()], args.format)
        elif args.cmd == "stats":
            _emit(bank.stats(), args.format)
        else:  # pragma: no cover - argparse enforces required subcommand
            parser.error("unknown command")
    except MemoryBankError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
