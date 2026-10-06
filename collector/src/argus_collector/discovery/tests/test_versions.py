"""Country versions of a site (owner 06.10.2026): which version a page is, where the
exhibition country's version is, in the owner's order."""

from __future__ import annotations

from argus_collector.discovery import contract as discovery
from argus_collector.discovery.contract import Candidate

BR = "https://www.gavazzi.example/en-br/products/"
HTML = """<html lang="en-BR"><head>
<link rel="alternate" hreflang="pt-br" href="/pt-br/products/">
<link rel="alternate" hreflang="fi" href="https://www.gavazzi.example/fi/tuotteet/">
<link rel="alternate" hreflang="en-fi" href="/en-fi/products/">
<link rel="alternate" hreflang="x-default" href="/en/products/">
</head><body></body></html>"""


def link(text: str, href: str) -> Candidate:
    return Candidate(index=1, kind="link", text=text, href=href, selector="a")


def test_which_country_a_page_is() -> None:
    assert discovery.page_country(BR, "en-BR") == "BR"
    assert discovery.page_country("https://wera.example/ru/", "ru") == "RU"
    assert discovery.page_country("https://reimax.example/", "en") is None, "global"
    assert discovery.page_country("https://beckhoff.example/en-en/", "en") is None
    assert discovery.page_country("https://malux.example/fi/", "fi") == "FI"
    assert discovery.page_country("https://shop.example.fi/", "en") == "FI"
    assert discovery.version_label(BR) == "en-br"


def test_hreflang_first_a_region_tag_before_the_language() -> None:
    local, world = discovery.version_candidates(BR, HTML, [], "FI", ["fi", "en"], True)
    urls = [u for u, _ in local]
    assert urls[:2] == ["https://www.gavazzi.example/en-fi/products/",
                        "https://www.gavazzi.example/fi/tuotteet/"]
    assert world[0] == "https://www.gavazzi.example/en/products/", "x-default"


def test_switcher_then_locale_paths_then_a_nordic_page() -> None:
    links = [link("Brasil", "/en-br/"), link("Suomi", "https://www.gavazzi.example/fi-fi/"),
             link("Our Nordic office", "https://www.gavazzi.example/en-br/nordic/")]
    local, world = discovery.version_candidates(BR, "<html></html>", links, "FI", ["fi", "en"],
                                                True)
    assert local[0] == ("https://www.gavazzi.example/fi-fi/", True), "the switcher"
    built = [u for u, strict in local[1:4]]
    assert built == ["https://www.gavazzi.example/fi/products/",
                     "https://www.gavazzi.example/en-fi/products/"] + built[2:], built
    assert ("https://www.gavazzi.example/en-br/nordic/", False) == local[-1], "any URL"
    assert world == ["https://www.gavazzi.example/en/products/"]


def test_a_site_without_locale_paths_gets_no_guessed_urls() -> None:
    local, world = discovery.version_candidates("https://reimax.example/contact/",
                                                "<html></html>", [], "FI", ["fi", "en"], True)
    assert local == [] and world == []


def test_a_global_page_is_left_only_for_a_version_it_names() -> None:
    """Beckhoff `/en-en/`: no guessed `/fi-fi/`, the walk keeps its way to Finland."""
    nordic = [link("Nordic sales", "https://beckhoff.example/en-en/nordic/")]
    local, _ = discovery.version_candidates("https://beckhoff.example/en-en/", "<html></html>",
                                            nordic, "FI", ["fi", "en"], False)
    assert local == []
    named = [link("Suomi", "https://beckhoff.example/fi-fi/")]
    local, _ = discovery.version_candidates("https://beckhoff.example/en-en/", "<html></html>",
                                            named, "FI", ["fi", "en"], False)
    assert local == [("https://beckhoff.example/fi-fi/", True)]
