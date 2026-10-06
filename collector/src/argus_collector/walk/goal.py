"""Has the walk reached its goal? Asked before every next action (owner 06.10.2026).

The tally holds every person read so far: a sales / marketing title or not,
and the person's own channels printed on the site (an address built from a
stated pattern is not one, `patterns.py`). A sales or marketing person with a
printed channel is the goal: the walk ends completed at once. People without
it (no channel, or no such role) allow 2 more pages, then the walk ends. An
unvisited link alone is no reason to go on.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from argus_collector.extraction import contract as extraction
from argus_collector.walk.service import END_GOAL, END_GOAL_PAGES

EXTRA_PAGES = 2
SALES_WORDS = (  # folded: no diacritics, lower case
    "sales", "marketing", "account manager", "key account", "export", "business development",
    "commercial", "area manager", "country manager",
    "myynti", "myyja", "markkinointi", "vienti", "kaupallinen", "asiakkuus",
    "vertrieb", "verkauf", "forsaljning", "salj", "marknad", "salg", "markeds",
    "vente", "ventas", "comercial", "verkoop",
)


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def is_sales(title: str) -> bool:
    folded = fold(title)
    return any(word in folded for word in SALES_WORDS)


@dataclass
class Tally:
    people: dict[str, tuple[bool, frozenset[str]]] = field(default_factory=dict)
    first_page: int | None = None  # the page count when the first person was read

    @property
    def channels(self) -> int:
        return sum(len(values) for _sales, values in self.people.values())

    @property
    def reached(self) -> bool:
        return any(sales and values for sales, values in self.people.values())


def note(tally: Tally, key: str, contact: extraction.Contact, built: bool, pages: int) -> None:
    """One person read on the page counted `pages`; `built`: its email came from a pattern."""
    sales, values = tally.people.get(key, (False, frozenset()))
    sales = sales or (contact.title is not None and is_sales(contact.title.value))
    own = [contact.phone] + ([] if built else [contact.email])
    values = values | {f.value for f in own if f is not None}
    tally.people[key] = (sales, values)
    if tally.first_page is None:
        tally.first_page = pages


def verdict(tally: Tally, pages: int) -> str | None:
    """END_GOAL, END_GOAL_PAGES (2 more pages read without the goal) or None: go on."""
    if not tally.people:
        return None
    if tally.reached:
        return END_GOAL
    first = tally.first_page if tally.first_page is not None else pages
    return END_GOAL_PAGES if pages - first >= EXTRA_PAGES else None
