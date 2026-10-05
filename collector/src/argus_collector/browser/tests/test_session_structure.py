"""Walk session: tabs, accordions and dropdowns as candidates, select, bot-check wait."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from argus_collector.browser import contract as browser
from argus_collector.browser import service

PAGE = """<html><body>
<div role="tablist">
 <button role="tab" id="t1" aria-selected="true" aria-controls="p1">Myynti</button>
 <button role="tab" id="t2" aria-selected="false" aria-controls="p2">Hallinto</button>
</div>
<div role="tabpanel" id="p1" aria-labelledby="t1"><h3>Kotimaa</h3>
 <div class="person">Anna Myyja <a href="tel:+358401111111">040 111 1111</a></div></div>
<div role="tabpanel" id="p2" aria-labelledby="t2" hidden>
 <div class="person">Joakim Johtaja <a href="tel:+358402222222">040 222 2222</a></div></div>
<h3><button type="button" aria-expanded="false" aria-controls="c-fi">Finland</button></h3>
<div id="c-fi" hidden>LEDVANCE Oy</div>
<label for="country">Choose your country</label>
<select id="country"><option value=""></option><option>Austria</option><option>Finland</option>
</select><div id="out"></div>
<script>
for (const tab of document.querySelectorAll('[role=tab]')) tab.addEventListener('click', () => {
  for (const t of document.querySelectorAll('[role=tab]')) {
    t.setAttribute('aria-selected', String(t === tab));
    document.getElementById(t.getAttribute('aria-controls')).hidden = t !== tab;
  }
});
document.querySelector('[aria-controls=c-fi]').addEventListener('click', e => {
  e.target.setAttribute('aria-expanded', 'true'); document.getElementById('c-fi').hidden = false;
});
document.getElementById('country').addEventListener('change', e => {
  document.getElementById('out').innerText = 'Office of ' + e.target.value;
});
</script></body></html>"""

CHALLENGE = """<html><head><title>Just a moment...</title></head><body>
<div id="challenge-running">Checking your browser before accessing the site.</div>
<script>setTimeout(() => { document.title = 'Yhteystiedot';
  document.body.innerHTML = '<h1>Yhteystiedot</h1>' + '<p>Asiakaspalvelu</p>'.repeat(3); },
  __DELAY__);</script></body></html>"""


@pytest.fixture
def wb(tmp_path: Path) -> Iterator[browser.WalkBrowser]:
    with browser.WalkBrowser(headless=True, profile_dir=tmp_path / "profile") as session:
        yield session


def _page(tmp_path: Path, name: str, html: str) -> str:
    path = tmp_path / name
    path.write_text(html, encoding="utf-8")
    return path.as_uri()


def test_tabs_accordion_and_select_are_candidates(
    wb: browser.WalkBrowser, tmp_path: Path
) -> None:
    page = wb.goto(_page(tmp_path, "tabs.html", PAGE))
    by_text = {c.text: c for c in page.candidates}
    assert (by_text["Myynti"].role, by_text["Myynti"].state) == ("tab", "on")
    assert (by_text["Hallinto"].role, by_text["Hallinto"].state) == ("tab", "off")
    assert (by_text["Finland"].role, by_text["Finland"].state) == ("expand", "off")
    select = by_text["Choose your country"]
    assert select.kind == "select" and select.options == ("Austria", "Finland")
    after = wb.click(by_text["Hallinto"])
    assert "Joakim Johtaja" in after.text and "Anna Myyja" not in after.text
    probes = [browser.PersonProbe("Joakim Johtaja", (browser.ProbeValue(
        "040 222 2222", "phone", "+358402222222"),))]
    assert wb.bindings(probes)[0].group == "Hallinto", "no heading in the panel: its tab"
    chosen = wb.select(select, "Finland")
    assert "Office of Finland" in chosen.text


def test_bot_check_is_waited_out_or_reported(wb: browser.WalkBrowser, tmp_path: Path) -> None:
    cleared = wb.goto(_page(tmp_path, "check.html", CHALLENGE.replace("__DELAY__", "2500")))
    assert not cleared.challenge and cleared.title == "Yhteystiedot"
    stuck = wb.goto(_page(tmp_path, "stuck.html", CHALLENGE.replace("__DELAY__", "999999")))
    assert stuck.challenge, "still a bot check after 20 s"


def test_challenge_needs_two_signals() -> None:
    title_only = {"title": "Please wait", "text": "Welcome to our shop", "length": 4000,
                  "markers": []}
    assert not service.is_challenge(title_only)
    short_page = {"title": "Kontakt", "text": "Kontakt", "length": 40, "markers": []}
    assert not service.is_challenge(short_page)
    real = {"title": "Just a moment...", "text": "Checking your browser", "length": 80,
            "markers": ["#challenge-running"]}
    assert service.is_challenge(real)
