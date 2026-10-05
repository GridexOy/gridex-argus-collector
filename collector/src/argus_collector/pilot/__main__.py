"""`python -m argus_collector.pilot [--batch ID] [--out FILE]`: the pilot tables;
`python -m argus_collector.pilot timing --log FILE [--out FILE]`: where the time went."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from argus_collector.pilot import contract
from argus_collector.storage import contract as storage


def _write(text: str, out: Path | None, what: str) -> None:
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"{what} written: {out}")
    else:
        print(text, end="")


def _pilot(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="argus_collector.pilot")
    parser.add_argument("--batch", default=None, help="batch id (default: the latest batch)")
    parser.add_argument("--out", type=Path, default=None, help="write the markdown here")
    parser.add_argument("--sample", type=int, default=10, help="phones to check")
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--db", type=Path, default=None, help="collector.db (default: user data)")
    args = parser.parse_args(argv)
    conn = storage.connect(args.db)
    try:
        text = contract.render_markdown(contract.report(conn, args.batch, args.sample, args.seed))
    finally:
        conn.close()
    _write(text, args.out, "pilot report")
    return 0


def _timing(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="argus_collector.pilot timing")
    parser.add_argument("--log", type=Path, required=True, help="logs/collector-<date>.log")
    parser.add_argument("--out", type=Path, default=None, help="write the markdown here")
    parser.add_argument("--db", type=Path, default=None, help="collector.db for company names")
    parser.add_argument("--no-db", action="store_true", help="show job ids, not company names")
    args = parser.parse_args(argv)
    names: dict[str, str] = {}
    if not args.no_db:
        conn = storage.connect(args.db)
        try:
            names = contract.company_names(conn)
        finally:
            conn.close()
    lines = args.log.read_text(encoding="utf-8", errors="replace").splitlines()
    _write(contract.timing_markdown(lines, names, args.log.name), args.out, "timing report")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == ["timing"]:
        return _timing(argv[1:])
    return _pilot(argv)


if __name__ == "__main__":
    raise SystemExit(main())
