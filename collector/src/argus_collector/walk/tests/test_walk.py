"""Walk: pure rules, and the integration walk of the fixture site with the fake model."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from argus_collector.discovery.contract import Candidate
from argus_collector.storage import contract as storage
from argus_collector.walk import contract, service
from argus_collector.walk.tests.conftest import settings_for
from argus_collector.walk.tests.fake_policy import GoldPolicy
from collector.tests.fake_model_server import FakeModelServer


def link(i: int, text: str, href: str) -> Candidate:
    return Candidate(i, "link", text, href, f'[data-argus-idx="{i}"]')


def test_validate_start_url() -> None:
    assert contract.validate_start_url(" example.com ") == "https://example.com"
    assert contract.validate_start_url("http://127.0.0.1:8765/") == "http://127.0.0.1:8765/"
    assert contract.validate_start_url("") is None
    assert contract.validate_start_url("not a url") is None
    assert contract.validate_start_url("ftp://x.example") is None


def _rows(
    contacts: list[contract.WalkEvent],
) -> dict[tuple[str, str | None, str | None], contract.WalkEvent]:
    rows = {}
    for event in contacts:
        c = event.contact
        assert c is not None
        rows[
            (c.name.value, c.email.value if c.email else None, c.phone.value if c.phone else None)
        ] = event
    return rows


def test_walk_finds_every_gold_person_with_evidence(
    site: str, tmp_path: Path, gold: dict[str, Any]
) -> None:
    policy = GoldPolicy(gold["persons"])
    fake = FakeModelServer(policy).start()
    events: list[contract.WalkEvent] = []
    settings = settings_for(site, fake, tmp_path)
    try:
        summary = contract.run_walk(settings, events.append, lambda: False)
    finally:
        fake.stop()
    assert summary.error == "" and not summary.stopped
    assert events[-1].kind == service.EVENT_DONE
    contacts = [e for e in events if e.kind == service.EVENT_CONTACT]
    rows = _rows(contacts)
    for person in gold["persons"]:
        assert (person["name"], person["email"], person["phone"]) in rows, person["name"]
    assert not any(e.contact and e.contact.name.value == "Ghost Person" for e in contacts)
    assert len(contacts) == len(gold["persons"]), "no duplicate or channel-less contact rows"
    assert all(e.contact and (e.contact.phone or e.contact.email) for e in contacts), (
        "every emitted contact must carry at least one verified channel"
    )
    assert all("linkedin" not in u for u in summary.visited) and summary.pages <= 10
    assert {u.rsplit("/", 1)[-1] for u in summary.visited} >= {
        "team.html",
        "team-2.html",
        "contact.html",
    }
    steps = [
        e.detail for e in events if e.kind == service.EVENT_STEP and e.step == service.STEP_CLICK
    ]
    assert steps == ["Näytä yhteystiedot"]
    _check_evidence(tmp_path, contacts, policy)


def _check_evidence(tmp_path: Path, contacts: list[contract.WalkEvent], policy: GoldPolicy) -> None:
    conn = storage.connect(tmp_path / "collector.db")
    for event in contacts:
        row = conn.execute(
            "SELECT text_path FROM evidence_manifest WHERE evidence_id = ?", (event.evidence_id,)
        ).fetchone()
        assert row is not None and Path(row["text_path"]).is_file()
        text = Path(row["text_path"]).read_text(encoding="utf-8")
        assert event.contact is not None
        for field in (
            event.contact.name,
            event.contact.title,
            event.contact.email,
            event.contact.phone,
        ):
            if field is not None and field.start >= 0:
                assert text[field.start : field.end] == field.quote
    observed = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert observed == len(contacts)
    calls = conn.execute(
        "SELECT COUNT(*), SUM(cost_eur), MIN(prompt_tokens) FROM model_calls"
    ).fetchone()
    assert calls[0] == policy.card_calls + policy.action_calls and calls[1] == 0 and calls[2] > 0
    run = conn.execute("SELECT result, pages FROM runs").fetchone()
    assert run["result"] == "completed" and run["pages"] >= 4


def test_walk_stops_on_request_and_on_stop_file(
    site: str, tmp_path: Path, gold: dict[str, Any]
) -> None:
    fake = FakeModelServer(GoldPolicy(gold["persons"])).start()
    events: list[contract.WalkEvent] = []
    try:
        settings = settings_for(site, fake, tmp_path)
        summary = contract.run_walk(settings, events.append, lambda: True)
        assert summary.stopped and events[-1].kind == service.EVENT_STOPPED
        (tmp_path / "STOP").write_text("", encoding="utf-8")
        events.clear()
        summary = contract.run_walk(settings, events.append, lambda: False)
        assert summary.stopped and summary.pages <= 1
    finally:
        fake.stop()


def test_walk_reports_model_down_as_error(site: str, tmp_path: Path) -> None:
    fake = FakeModelServer(lambda s, u: "{}").start()
    fake.stop()
    events: list[contract.WalkEvent] = []
    summary = contract.run_walk(settings_for(site, fake, tmp_path), events.append, lambda: False)
    assert summary.error == "" and events[-1].kind == service.EVENT_DONE
    failed = [e for e in events if e.kind == service.EVENT_STEP and "failed" in e.detail]
    assert failed, "a dead model endpoint is reported in the step line, the walk falls back"
