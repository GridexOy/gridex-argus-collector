"""`python -m argus_collector.pilot [--batch ID] [--out FILE]`: the pilot tables."""

from __future__ import annotations

import argparse
from pathlib import Path

from argus_collector.pilot import contract
from argus_collector.storage import contract as storage


def main() -> int:
    parser = argparse.ArgumentParser(prog="argus_collector.pilot")
    parser.add_argument("--batch", default=None, help="batch id (default: the latest batch)")
    parser.add_argument("--out", type=Path, default=None, help="write the markdown here")
    parser.add_argument("--sample", type=int, default=10, help="phones to check")
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--db", type=Path, default=None, help="collector.db (default: user data)")
    args = parser.parse_args()
    conn = storage.connect(args.db)
    try:
        text = contract.render_markdown(contract.report(conn, args.batch, args.sample, args.seed))
    finally:
        conn.close()
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"pilot report written: {args.out}")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
