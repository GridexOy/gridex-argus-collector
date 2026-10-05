"""worker_auth: the one-string pairing key `argus://pair?url=&worker=&token=`."""

from __future__ import annotations

from pathlib import Path

import pytest

from argus_collector.worker_auth import contract
from contract_server import server as contract_server

PROD = "argus://pair?url=https%3A%2F%2Fargus.example.fi&worker=worker-main-pc&token=abc%2B1%2F2="


def test_key_from_argus_is_parsed() -> None:
    key = contract.parse_pairing_key(f"  {PROD}\n")
    assert key == contract.PairingKey("https://argus.example.fi", "worker-main-pc", "abc+1/2=")


def test_plus_stays_plus_and_raw_url_is_accepted() -> None:
    key = contract.parse_pairing_key(
        "argus://pair?url=https://argus.example.fi/api/collector/&worker=w1&token=a+b"
    )
    assert key == contract.PairingKey("https://argus.example.fi", "w1", "a+b")


def test_stand_key_round_trips() -> None:
    text = contract_server.pairing_key("http://127.0.0.1:8900", "worker-main-pc", "test-token-abc")
    key = contract.parse_pairing_key(text)
    assert key == contract.PairingKey("http://127.0.0.1:8900", "worker-main-pc", "test-token-abc")


@pytest.mark.parametrize(
    ("text", "reason", "field"),
    [
        ("", contract.REASON_FORMAT, ""),
        ("https://argus.example.fi", contract.REASON_FORMAT, ""),
        ("argus://other?url=https://a.fi&worker=w&token=t", contract.REASON_FORMAT, ""),
        ("argus://pair", contract.REASON_FORMAT, ""),
        ("argus://pair?url=https://a.fi&token=t", contract.REASON_MISSING, "worker"),
        ("argus://pair?url=https://a.fi&worker=w&token=", contract.REASON_MISSING, "token"),
        ("argus://pair?url=https://a.fi&worker=w&worker=x&token=t",
         contract.REASON_DUPLICATE, "worker"),
        ("argus://pair?url=https://a.fi&worker=w%20x&token=t", contract.REASON_CHARACTERS,
         "worker"),
        ("argus://pair?url=https://a.fi&worker=w&token=t%0D%0AX", contract.REASON_CHARACTERS,
         "token"),
        ("argus://pair?url=ftp://a.fi&worker=w&token=t", contract.REASON_URL, "url"),
        ("argus://pair?url=argus.fi&worker=w&token=t", contract.REASON_URL, "url"),
        ("argus://pair?url=http://argus.example.fi&worker=w&token=t", contract.REASON_HTTPS,
         "url"),
    ],
)
def test_bad_keys_are_refused_with_a_reason(text: str, reason: str, field: str) -> None:
    with pytest.raises(contract.PairingKeyError) as caught:
        contract.parse_pairing_key(text)
    assert (caught.value.reason, caught.value.field) == (reason, field)


def test_http_only_for_this_pc() -> None:
    key = contract.parse_pairing_key("argus://pair?url=http://localhost:8900&worker=w&token=t")
    assert key.base_url == "http://localhost:8900"
    assert contract.is_loopback("http://127.0.0.1:8900")
    assert not contract.is_loopback("https://argus.example.fi")


def test_save_pairing_keeps_address_worker_and_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ARGUS_COLLECTOR_HOME", str(tmp_path))
    contract.save_pairing(contract.parse_pairing_key(PROD))
    assert contract.load_connection() == contract.SavedConnection(
        "https://argus.example.fi", "worker-main-pc"
    )
    assert contract.load_token() == "abc+1/2="
    assert "abc+1/2=" not in (tmp_path / "worker_connection.json").read_text(encoding="utf-8")
