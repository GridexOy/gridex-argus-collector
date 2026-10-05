"""Job-mode walks: approved hosts from the job, country focus, findings to a sink."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from argus_collector.discovery import contract as discovery
from argus_collector.models.contract import CallRecord, ModelConfig
from argus_collector.walk import contract
from argus_collector.walk.tests.fake_policy import RankedPolicy
from collector.tests.fake_model_server import FakeModelServer
from test_site import server

GOLD_DIR = Path(__file__).resolve().parents[5] / "test_site" / "gold"


class RecordingSink:
    def __init__(self) -> None:
        self.sources: list[contract.PageSource] = []
        self.findings: list[contract.PageFindings] = []
        self.gaps: list[contract.WalkGap] = []
        self.calls: list[CallRecord] = []
        self.checkpoints = 0

    def page_stored(self, conn: sqlite3.Connection, source: contract.PageSource) -> None:
        self.sources.append(source)

    def page_done(self, conn: sqlite3.Connection, findings: contract.PageFindings) -> None:
        assert conn.in_transaction, "findings are written in the walk's transaction"
        self.findings.append(findings)

    def gap(self, conn: sqlite3.Connection, gap: contract.WalkGap) -> None:
        self.gaps.append(gap)

    def model_called(self, conn: sqlite3.Connection, record: CallRecord) -> None:
        self.calls.append(record)

    def checkpoint(self, conn: sqlite3.Connection, checkpoint: contract.WalkCheckpoint) -> None:
        self.checkpoints += 1

    def entities(self) -> dict[str, contract.EntityFinding]:
        return {e.entity_key: e for f in self.findings for e in f.entities}


def gold(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((GOLD_DIR / f"{name}.json").read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def site() -> Iterator[ThreadingHTTPServer]:
    srv = server.start(port=0)
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def walk(
    srv: ThreadingHTTPServer, label: str, host: str, tmp_path: Path, pages: int = 12
) -> tuple[contract.WalkSummary, RecordingSink]:
    persons = [p for name in ("nordtec", "vogel") for p in gold(name)["persons"]]
    fake = FakeModelServer(RankedPolicy(persons)).start()
    sink = RecordingSink()
    settings = contract.WalkSettings(
        start_url=server.vhost_url(srv, label),
        model=ModelConfig(fake.endpoint, "fake-instruct"),
        headless=True,
        profile_dir=tmp_path / "profile",
        evidence_dir=tmp_path / "evidence",
        db_path=tmp_path / "collector.db",
        approved_hosts=frozenset({host}),
        focus=discovery.make_focus(["FI"], ["fi", "en"]),
        limits=contract.WalkLimits(pages=pages, actions=40, seconds=600.0, states=60),
        id_namespace="job-" + label,
    )
    try:
        summary = contract.run_walk(settings, lambda e: None, lambda: False, sink)
    finally:
        fake.stop()
    return summary, sink


def page_order(sink: RecordingSink) -> list[str]:
    paths = []
    for source in sink.sources:
        path = source.url.split("/", 3)[3]
        if path not in paths:
            paths.append(path)
    return paths


def test_finnish_version_and_office_first(site: ThreadingHTTPServer, tmp_path: Path) -> None:
    summary, sink = walk(site, "nordtec", "nordtec.localhost", tmp_path)
    order = page_order(sink)
    assert order[:3] == ["", "fi/", "fi/yhteystiedot.html"], order
    assert all(order.index(p) > order.index("fi/yhteystiedot.html") for p in order if "sv/" in p)
    entities = sink.entities()
    for person in gold("nordtec")["persons"]:
        ent = entities[person["name"].casefold()]
        values = {f.field: f for f in ent.fields}
        assert values["phone"].value == person["phone"] and values["email"].value == person["email"]
        assert values["phone"].binding == "card" and values["phone"].status == "confirmed"
    footer = entities["organization_channel:phone|+35895551200"]
    assert footer.fields[0].binding == "caption", "Vaihde line: the company's number"
    assert "organization_channel:email|info.fi@nordtec.example" in entities
    assert summary.end_reason in (contract.END_FINISHED, contract.END_BUDGET)
    assert {c.purpose for c in sink.calls} == {"walk.cards", "walk.action"}
    assert sink.checkpoints >= len(order)


def test_every_found_field_is_in_the_page_audit(
    site: ThreadingHTTPServer, tmp_path: Path
) -> None:
    _, sink = walk(site, "nordtec", "nordtec.localhost", tmp_path, pages=4)
    for findings in sink.findings:
        audited = {o for item in findings.audit for o in item.observation_ids}
        for entity in findings.entities:
            for field in entity.fields:
                assert field.observation_id in audited
                if field.start >= 0:
                    assert findings.source.text[field.start : field.end] == field.raw


def test_company_without_office_reads_export_people_in_own_language(
    site: ThreadingHTTPServer, tmp_path: Path
) -> None:
    summary, sink = walk(site, "vogel", "vogel.localhost", tmp_path)
    order = page_order(sink)
    assert order[1] == "export.html", order
    if "fr/" in order:
        assert order.index("fr/") > order.index("en/contact.html")
    entities = sink.entities()
    for person in gold("vogel")["persons"]:
        if person["priority"] or person["source_page"] in order:
            ent = entities[person["name"].casefold()]
            phone = next(f for f in ent.fields if f.field == "phone")
            assert phone.value == person["phone"], "national numbers read as German (lang de)"
    assert summary.checkpoint.native_language == "de"
    assert summary.checkpoint.consents == {"vogel.localhost": "necessary: Nur notwendige"}


def test_seed_redirect_off_the_approved_host_is_a_gap(
    site: ThreadingHTTPServer, tmp_path: Path
) -> None:
    summary, sink = walk(site, "katsa-oy", "katsa-oy.localhost", tmp_path)
    assert summary.end_reason == contract.END_DOMAIN
    assert [g.reason for g in summary.gaps] == ["domain_ownership_unresolved"]
    assert "katsa-group.localhost" in summary.gaps[0].detail
    assert sink.findings == [] and sink.sources == [], "nothing of that host is recorded"
