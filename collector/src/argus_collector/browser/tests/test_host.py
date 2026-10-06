"""One Chrome per collection, a clean context per company (owner 06.10.2026)."""

from __future__ import annotations

from collections.abc import Iterator
from http.server import ThreadingHTTPServer

import pytest

from argus_collector.browser import contract as browser
from test_site import server


@pytest.fixture(scope="module")
def site() -> Iterator[ThreadingHTTPServer]:
    srv = server.start(port=0)
    try:
        yield srv
    finally:
        srv.shutdown()
        srv.server_close()


def test_one_start_and_clean_cookies_per_company(site: ThreadingHTTPServer) -> None:
    host = browser.BrowserHost(headless=True)
    url = server.base_url(site)
    try:
        with browser.WalkBrowser(True, host=host) as first:
            first.goto(url)
            first.page.context.add_cookies([{"name": "seen", "value": "1", "url": url}])
            assert first.start_ms > 0, "the first walk starts Chrome"
        assert host.running, "closing the walk closes its context, not the browser"
        with browser.WalkBrowser(True, host=host) as second:
            second.goto(url)
            assert second.page.context.cookies() == [], "the next company starts clean"
            assert second.start_ms == 0, "no second start"
        assert (host.starts, host.start_ms > 0) == (1, True)
    finally:
        host.close()
    assert not host.running


def test_a_browser_that_died_is_started_again(site: ThreadingHTTPServer) -> None:
    host = browser.BrowserHost(headless=True)
    try:
        with browser.WalkBrowser(True, host=host):
            pass
        host.close()  # as if Chrome had died between two companies
        with browser.WalkBrowser(True, host=host) as again:
            again.goto(server.base_url(site))
            assert again.start_ms > 0
        assert host.starts == 2
    finally:
        host.close()
