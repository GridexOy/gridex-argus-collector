"""Server features: port placeholder, variants, bot check, no directory listings."""

from __future__ import annotations

import difflib
from collections.abc import Iterator
from http.server import ThreadingHTTPServer

import pytest

from test_site import pages, server
from test_site.tests.client import CHALLENGE_TITLE, WAF_PASS, port_of, request, running

CHALLENGE_MARKERS = (
    CHALLENGE_TITLE,
    '<div id="challenge-running">',
    "<noscript>Enable JavaScript and cookies to continue</noscript>",
    '<meta name="robots" content="noindex, nofollow">',
    "Checking your browser before accessing ledvance.localhost.",
    "This process is automatic. Your browser will redirect to your requested content shortly.",
    "}, 3000);",
    "location.reload();",
)
SETS_COOKIE = 'document.cookie = "fixture_waf=passed; path=/";'


@pytest.fixture(scope="module")
def site() -> Iterator[ThreadingHTTPServer]:
    with running() as srv:
        yield srv


def test_port_placeholder_becomes_the_port_of_each_server() -> None:
    with running() as one, running() as two:
        assert port_of(one) != port_of(two)
        for srv in (one, two):
            reply = request(srv, "malux.localhost", "/fi/")
            assert reply.status == 200
            assert f'href="http://malux-se.localhost:{port_of(srv)}/sv/"' in reply.text
            assert "__PORT__" not in reply.text
            assert int(reply.headers["content-length"]) == len(reply.body)
            head = request(srv, "malux.localhost", "/fi/", method="HEAD")
            assert head.body == b"" and head.headers["content-length"] == str(len(reply.body))


def test_port_comes_from_the_host_header_else_from_the_server(site: ThreadingHTTPServer) -> None:
    named = request(site, "malux-se.localhost", "/sv/", host_port="9999").text
    assert 'href="http://malux.localhost:9999/fi/"' in named
    bare = request(site, "malux-se.localhost", "/sv/", host_port="").text
    assert f'href="http://malux.localhost:{port_of(site)}/fi/"' in bare


def test_folder_without_slash_redirects_and_folders_are_never_listed(
    site: ThreadingHTTPServer,
) -> None:
    moved = request(site, "malux.localhost", "/fi")
    assert moved.status == 301 and moved.headers["location"].endswith("/fi/")
    assert request(site, "ledvance.localhost", "/en-int/").status == 404
    assert request(site, "malux-se.localhost", "/sv/kontakt/nope/").status == 404
    assert request(site, "127.0.0.1", "/style.css").headers["content-type"] == "text/css"


def test_departed_variant_drops_only_pekka_salo(site: ThreadingHTTPServer) -> None:
    with running("departed") as departed:
        before = request(site, "127.0.0.1", "/team.html").text
        after = request(departed, "127.0.0.1", "/team.html").text
        assert "Pekka Salo" in before and "Pekka Salo" not in after
        assert "Liisa Mäkelä" in after and "Seuraava sivu" in after
        diff = difflib.ndiff(before.splitlines(), after.splitlines())
        changed = [line for line in diff if line[:2] in ("- ", "+ ")]
        assert len(changed) == 5 and all(line.startswith("- ") for line in changed)
        assert 'data-user="pekka.salo"' in changed[0]
        others = [("127.0.0.1", "/"), ("127.0.0.1", "/contact.html"), ("127.0.0.1", "/style.css")]
        others += [("nordtec.localhost", "/fi/yhteystiedot.html"), ("malux.localhost", "/fi/")]
        same_port = str(port_of(site))  # the same Host header, so `__PORT__` matches too
        for host, path in others:
            normal = request(site, host, path).body
            assert normal == request(departed, host, path, host_port=same_port).body


def test_variants_are_checked() -> None:
    assert pages.known_variants() == ["challenge-stuck", "departed"]
    with pytest.raises(ValueError, match="unknown test site variant"):
        server.make_server(port=0, variant="nope")


def test_bot_check_without_the_cookie_answers_the_interstitial(site: ThreadingHTTPServer) -> None:
    for path, cookie in (("/fi-fi/", ""), ("/fi-fi/yhteystiedot/", "fixture_waf=nope")):
        reply = request(site, "ledvance.localhost", path, cookie)
        assert reply.status == 200
        for marker in (*CHALLENGE_MARKERS, SETS_COOKIE):
            assert marker in reply.text, marker
        assert "Kari Lehtonen" not in reply.text and "Yhteystiedot" not in reply.text
        assert reply.headers["cache-control"] == "no-store"
    head = request(site, "ledvance.localhost", "/fi-fi/", method="HEAD")
    assert head.body == b"" and int(head.headers["content-length"]) > 0


def test_bot_check_passes_with_the_cookie(site: ThreadingHTTPServer) -> None:
    reply = request(site, "ledvance.localhost", "/fi-fi/yhteystiedot/", f"lang=fi; {WAF_PASS}")
    assert reply.status == 200 and "Kari Lehtonen" in reply.text
    assert CHALLENGE_TITLE not in reply.text


def test_bot_check_guards_only_the_finnish_ledvance_pages(site: ThreadingHTTPServer) -> None:
    for host, path in (
        ("ledvance.localhost", "/"),
        ("ledvance.localhost", "/en-int/company/contact/"),
        ("malux.localhost", "/fi/"),
        ("127.0.0.1", "/team.html"),
    ):
        reply = request(site, host, path)
        assert reply.status == 200 and CHALLENGE_TITLE not in reply.text


def test_challenge_stuck_never_sets_nor_accepts_the_cookie() -> None:
    with running("challenge-stuck") as srv:
        for cookie in ("", WAF_PASS):
            reply = request(srv, "ledvance.localhost", "/fi-fi/yhteystiedot/", cookie)
            assert reply.status == 200
            for marker in CHALLENGE_MARKERS:
                assert marker in reply.text, marker
            assert "document.cookie" not in reply.text
        assert "Kari Lehtonen" not in request(srv, "ledvance.localhost", "/fi-fi/", WAF_PASS).text
        assert "Contact LEDVANCE worldwide" in request(
            srv, "ledvance.localhost", "/en-int/company/contact/"
        ).text
