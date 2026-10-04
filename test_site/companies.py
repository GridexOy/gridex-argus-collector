"""Fixture companies of the test site as batch input for contract_server.stand.

`companies(port)` lists one entry per fixture company (seed URL, approved
hosts, scope priorities); `python -m test_site.companies [--port 8765]`
prints it as JSON, and `companies.json` is that output for the default port
(a test keeps the two equal). Exhibition country of the fixtures: Finland.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_PORT = 8765
JSON_FILE = Path(__file__).resolve().parent / "companies.json"
FI_SCOPE = {"priority_countries": ["FI"], "priority_languages": ["fi", "en"]}


def _company(company_id: str, name: str, seed: str, hosts: list[str]) -> dict[str, Any]:
    return {
        "company_id": company_id,
        "company_name": name,
        "seed_urls": [seed],
        "approved_hosts": hosts,
        **FI_SCOPE,
        "project_id": "fixture-expo-2027",
    }


def companies(port: int = DEFAULT_PORT) -> list[dict[str, Any]]:
    def vhost(label: str) -> str:
        return f"http://{label}.localhost:{port}/"

    return [
        _company("fixture_oy", "Fixture Oy", f"http://127.0.0.1:{port}/", ["127.0.0.1"]),
        _company("nordtec", "Nordtec AB", vhost("nordtec"), ["nordtec.localhost"]),
        _company("vogel", "Vogel Antriebstechnik GmbH", vhost("vogel"), ["vogel.localhost"]),
        _company("katsa", "Katsa Oy", vhost("katsa-oy"), ["katsa-oy.localhost"]),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the fixture companies as JSON")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    print(json.dumps(companies(args.port), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
