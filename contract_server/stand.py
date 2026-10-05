"""Owner-side CLI of the test stand: plays ARGUS's System role and prints JSON.

python -m contract_server.stand <subcommand> [--base-url URL] [--system-token T]
  batch --companies FILE.json [--only id1,id2] [--rerun-reason TEXT]
        [--client-request-id X]
  job JOB_ID | batch-status BATCH_ID | worker WORKER_ID | contacts JOB_ID
  company-contacts COMPANY_ID
  control JOB_ID pause|resume|cancel|continue
FILE.json is a list of {company_id, company_name, seed_urls,
approved_hosts: [host...], priority_countries, priority_languages, project_id?}.
Exit code 0 on a 2xx answer, 1 otherwise (the Error body is printed).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from contract_server.registry import DEFAULT_SYSTEM_TOKENS
from contract_server.util import Json

DESCRIPTION = "Owner-side CLI of the contract_server test stand (System role)"
DEFAULT_BASE_URL = "http://127.0.0.1:8900"
API = "/api/collector"
# Local stand: never use the system proxy (Windows answers 127.0.0.1 with 502).
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
DEFAULT_POLICY: Json = {
    "max_active_seconds": 1800,
    "max_pages": 200,
    "max_browser_actions": 400,
    "cloud_budget_eur": 0,
    "human_assistance": True,
    "auto_continue": False,
    "max_runs": 6,
    "max_campaign_active_seconds": 10800,
    "max_states": 300,
    "campaign_max_pages": 600,
    "campaign_max_states": 900,
    "campaign_max_browser_actions": 1200,
    "campaign_cloud_budget_eur": 0,
}


def call(
    args: argparse.Namespace, method: str, path: str, body: Json | None = None
) -> tuple[int, Any]:
    """One request; returns (status, parsed JSON body)."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Authorization": f"Bearer {args.system_token}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    url = args.base_url.rstrip("/") + path
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with OPENER.open(request, timeout=30) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return int(exc.code), json.loads(exc.read().decode("utf-8") or "{}")


def company_input(item: Json, rerun_reason: str | None) -> Json:
    company_id = str(item["company_id"])
    return {
        "company_id": company_id,
        "project_id": item.get("project_id"),
        "company_name": item["company_name"],
        "seed_urls": list(item["seed_urls"]),
        "scope": {
            "geography": "specified",
            "priority_countries": list(item.get("priority_countries", [])),
            "priority_languages": list(item.get("priority_languages", [])),
            "approved_hosts": [
                {"host": host, "basis": "seed", "evidence_id": None}
                for host in item["approved_hosts"]
            ],
            "include_contact_documents": False,
            "include_historical_observations": False,
        },
        "policy": dict(DEFAULT_POLICY),
        "participation_status": "confirmed",
        "participation_claim_id": f"stand-claim-{company_id}",
        "override_reason": None,
        "rerun_reason": rerun_reason,
    }


def batch_request(args: argparse.Namespace) -> Json:
    items: list[Json] = json.loads(Path(args.companies).read_text(encoding="utf-8"))
    if args.only:
        wanted = {part.strip() for part in args.only.split(",") if part.strip()}
        items = [item for item in items if str(item["company_id"]) in wanted]
    return {
        "client_request_id": args.client_request_id or str(uuid.uuid4()),
        "companies": [company_input(item, args.rerun_reason) for item in items],
    }


def run_command(args: argparse.Namespace) -> tuple[int, Any]:
    name = args.command
    if name == "batch":
        return call(args, "POST", f"{API}/batches", batch_request(args))
    if name == "control":
        return control(args)
    paths = {
        "job": f"{API}/jobs/{{}}",
        "batch-status": f"{API}/batches/{{}}",
        "worker": f"{API}/workers/{{}}/status",
        "contacts": "/_stand/jobs/{}/contacts",
        "company-contacts": "/_stand/companies/{}/contacts",
    }
    return call(args, "GET", paths[name].format(quote(args.target, safe="")))


def control(args: argparse.Namespace) -> tuple[int, Any]:
    job_path = f"{API}/jobs/{quote(args.target, safe='')}"
    status, job = call(args, "GET", job_path)
    if status != 200:
        return status, job
    body = {
        "client_request_id": str(uuid.uuid4()),
        "action": args.action,
        "expected_state_revision": job["state_revision"],
    }
    return call(args, "POST", f"{job_path}/control", body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="contract_server.stand", description=DESCRIPTION)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--base-url", default=DEFAULT_BASE_URL)
    common.add_argument("--system-token", default=sorted(DEFAULT_SYSTEM_TOKENS)[0])
    commands = parser.add_subparsers(dest="command", required=True)
    batch = commands.add_parser("batch", parents=[common], help="POST /batches")
    batch.add_argument("--companies", required=True, metavar="FILE.json")
    batch.add_argument("--only", default=None, metavar="ID1,ID2")
    batch.add_argument("--rerun-reason", default=None)
    batch.add_argument("--client-request-id", default=None)
    for name, metavar in (
        ("job", "JOB_ID"),
        ("batch-status", "BATCH_ID"),
        ("worker", "WORKER_ID"),
        ("contacts", "JOB_ID"),
        ("company-contacts", "COMPANY_ID"),
    ):
        commands.add_parser(name, parents=[common]).add_argument("target", metavar=metavar)
    ctl = commands.add_parser("control", parents=[common], help="POST /jobs/{id}/control")
    ctl.add_argument("target", metavar="JOB_ID")
    ctl.add_argument("action", choices=["pause", "resume", "cancel", "continue"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        status, payload = run_command(args)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
