"""Cookie banners: necessary cookies first, then reject, accept only as the last choice."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from argus_collector.browser import contract as browser
from argus_collector.browser import service

BANNER = """<html><body><h1>Yhteystiedot</h1><p>Puh. 020 123 4567</p>
<div id="onetrust-banner-sdk" role="dialog"><p>Käytämme evästeitä.</p>
__BUTTONS__</div>
<script>document.getElementById('onetrust-banner-sdk').addEventListener('click', e => {
  if (e.target.tagName === 'BUTTON') { document.title = 'chose ' + e.target.innerText;
    e.currentTarget.remove(); } });</script></body></html>"""


@pytest.fixture
def wb(tmp_path: Path) -> Iterator[browser.WalkBrowser]:
    with browser.WalkBrowser(headless=True, profile_dir=tmp_path / "profile") as session:
        yield session


@pytest.mark.parametrize(("buttons", "kind", "text"), [
    (("Hyväksy kaikki", "Vain välttämättömät", "Asetukset"), "necessary", "Vain välttämättömät"),
    (("Accept All Cookies", "Reject All", "Cookies Settings"), "reject", "Reject All"),
    (("OK", "Lue lisää"), "accept", "OK"),
])
def test_banner_is_answered_once(wb: browser.WalkBrowser, tmp_path: Path,
                                 buttons: tuple[str, ...], kind: str, text: str) -> None:
    html = BANNER.replace("__BUTTONS__", "".join(f"<button>{b}</button>" for b in buttons))
    page = tmp_path / f"{kind}.html"
    page.write_text(html, encoding="utf-8")
    state = wb.goto(page.as_uri())
    assert state.consent == f"{kind}: {text}" and state.title == f"chose {text}"
    assert "evästeitä" not in state.text, "the banner is gone before the page is read"


def test_choice_words_are_whole_words() -> None:
    assert service.consent_choice([{"index": 0, "text": "Cookie-asetukset"}]) is None
    assert service.consent_choice([{"index": 1, "text": "Nur notwendige"}]) == (
        1, "necessary", "Nur notwendige")
    assert service.consent_choice(None) is None
