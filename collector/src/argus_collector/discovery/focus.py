"""Exhibition-country focus of a walk (scope.priority_countries / priority_languages).

Owner decision 04.10.2026: switch to the site version of the exhibition
country and its local office; a company without an office there is read in
its own language and English, and the people sought are export / Nordic /
international sales and marketing. Pure: link scores and the prompt brief.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from urllib.parse import parse_qs, urlsplit

from argus_collector.discovery import repository as tables

WORD_RE = re.compile(r"[a-z]+")
LOCALE_RE = re.compile(r"^([a-z]{2})(?:[-_]([a-z]{2}))?$")
LANGUAGE_QUERY_KEYS = ("lang", "language", "locale", "hl")


@dataclass(frozen=True)
class Focus:
    """`countries[0]` is the exhibition country, `languages[0]` the preferred
    language; `native_language` is the language of the company's own seed page."""

    countries: tuple[str, ...]
    languages: tuple[str, ...]
    native_language: str = ""

    def with_native(self, language: str) -> Focus:
        return replace(self, native_language=fold(language).split("-", 1)[0][:2])


def make_focus(countries: list[str], languages: list[str]) -> Focus | None:
    """None when the scope names no priority at all (the walk then has no focus)."""
    codes = tuple(c.strip().upper() for c in countries if c.strip())
    langs = tuple(fold(lang).split("-", 1)[0][:2] for lang in languages if lang.strip())
    return Focus(codes, langs) if codes or langs else None


def fold(text: str) -> str:
    """Lower case without diacritics (`Français` -> `francais`)."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip()


def link_language(text: str, href: str) -> str | None:
    """Language a link switches to: its whole text names a language (`Suomi`,
    `English`, `FI`), or its path starts with a locale (`/fi/`, `/de-de/`), or a
    `lang=` style query parameter says so."""
    folded = fold(text)
    for language, names in tables.LANGUAGE_NAMES.items():
        if folded in names:
            return language
    parts = urlsplit(href)
    segment = parts.path.strip("/").split("/", 1)[0].lower()
    match = LOCALE_RE.match(segment)
    if match and match.group(1) in tables.LANGUAGE_NAMES:
        return match.group(1)
    query = parse_qs(parts.query)
    for key in LANGUAGE_QUERY_KEYS:
        value = fold(query.get(key, [""])[0])[:2]
        if value in tables.LANGUAGE_NAMES:
            return value
    return None


def _language_score(language: str | None, focus: Focus) -> int:
    if language is None:
        return 0
    if focus.languages and language == focus.languages[0]:
        return tables.FOCUS_FIRST_LANGUAGE_BONUS
    if language in focus.languages:
        return tables.FOCUS_OTHER_LANGUAGE_BONUS
    if language == focus.native_language:
        return 0
    return tables.FOCUS_FOREIGN_LANGUAGE_PENALTY


def _country_score(words: set[str], focus: Focus) -> int:
    for rank, country in enumerate(focus.countries):
        if words & set(tables.COUNTRY_WORDS.get(country, ())):
            return tables.FOCUS_COUNTRY_BONUS if rank == 0 else tables.FOCUS_COUNTRY_BONUS // 2
    return 0


def focus_score(text: str, href: str, focus: Focus | None) -> int:
    """Extra link score: preferred language / exhibition country / export people."""
    if focus is None:
        return 0
    text_words = set(WORD_RE.findall(fold(text)))
    path_words = set(WORD_RE.findall(fold(urlsplit(href).path)))
    score = _language_score(link_language(text, href), focus)
    score += _country_score(text_words | path_words, focus)
    export = sum(w for word, w in tables.EXPORT_WORDS.items() if word in text_words)
    export += sum(w // 2 for word, w in tables.EXPORT_WORDS.items() if word in path_words)
    return score + min(export, tables.FOCUS_EXPORT_CAP)


def country_name(code: str) -> str:
    return tables.COUNTRY_NAMES.get(code, code)


def focus_brief(focus: Focus | None) -> str:
    """English instructions for the model's action prompt (empty without focus)."""
    if focus is None or not focus.countries:
        return ""
    country = country_name(focus.countries[0])
    preferred = ", ".join(focus.languages) or "the local language"
    own = focus.native_language or "the company's own language"
    return (
        f"Exhibition country: {country} ({focus.countries[0]}); preferred languages: "
        f"{preferred}. Prefer, in this order: (1) the site version for {country} or in "
        f"{focus.languages[0] if focus.languages else 'its language'}; (2) the {country} "
        f"office or the contacts responsible for {country}; (3) when the company has no "
        f"office in {country}: pages in {own} or in English that list export, Nordic, "
        "Scandinavian or international sales and marketing people. Other language "
        "versions of the site come last."
    )
