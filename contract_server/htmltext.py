"""Evidence text for quote checks: HTML -> plain text, whitespace-insensitive search.

The derived text drops script/style, strips tags (each tag becomes a space),
unescapes character references and collapses whitespace. Quote search
ignores all whitespace on both sides.
"""

from __future__ import annotations

from html.parser import HTMLParser

SKIPPED_TAGS = frozenset({"script", "style"})


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIPPED_TAGS:
            self.skip_depth += 1
        self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIPPED_TAGS and self.skip_depth:
            self.skip_depth -= 1
        self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


def collapse(text: str) -> str:
    return " ".join(text.split())


def html_to_text(html: str) -> str:
    parser = _TextParser()
    parser.feed(html)
    parser.close()
    return collapse("".join(parser.parts))


def derive_text(raw: bytes, mime_type: str, source_kind: str) -> str:
    """Text of an upload without canonical_text: HTML is stripped, the rest decoded."""
    decoded = raw.decode("utf-8", errors="replace")
    if "html" in mime_type.lower() or source_kind in ("http_html", "browser_dom"):
        return html_to_text(decoded)
    return collapse(decoded)


def _squash(text: str) -> str:
    return "".join(text.split())


def quote_found(quote: str, *haystacks: str) -> bool:
    """A non-blank quote appears in one of the texts, ignoring all whitespace."""
    needle = _squash(quote)
    return bool(needle) and any(needle in _squash(text) for text in haystacks)
