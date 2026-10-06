"""Context fields of an entity: its country and its department (owner 05.10.2026).

The country of an office is the country heading of its section (quote: the
heading line); the country of a person is that of the section it sits in, or
the calling code of its phone (`+358` FI; quote: the phone), or the region the page
declares in `<html lang>` (`sv-SE`; quote: the attribute value, locator `html:lang`).
The department is the group heading or tab label of the person's card (`Johto`,
`Myynti`); a heading that is a country, a company name or a generic contact title
is not a department.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from argus_collector.discovery import contract as discovery
from argus_collector.evidence.contract import find_span
from argus_collector.extraction import contract as extraction
from argus_collector.normalization import contract as norm

LOCATOR_LANG = "html:lang"
LANG_REGION_RE = re.compile(r"^[a-z]{2}[-_]([a-z]{2})$", re.IGNORECASE)
DEPARTMENT_MAX_LEN = 60
NOT_DEPARTMENTS = frozenset({
    "yhteystiedot", "yhteyshenkilot", "henkilosto", "henkilokunta", "ota yhteytta",
    "contact", "contacts", "contact us", "our team", "team", "people", "staff",
    "kontakt", "kontakta oss", "medarbetare", "kontakte", "ansprechpartner",
})
LEGAL_WORDS = frozenset({"oy", "oyj", "ab", "gmbh", "ag", "ltd", "inc", "as", "a/s", "sa", "bv"})


@dataclass(frozen=True)
class PageContext:
    sections: tuple[extraction.Section, ...] = ()
    lang: str = ""  # `<html lang>` value as written in the snapshot
    patterns: tuple[extraction.EmailPattern, ...] = ()  # address patterns the page states


def lang_country(lang: str) -> str | None:
    match = LANG_REGION_RE.match(lang.strip())
    return discovery.label_country(match.group(1).upper()) if match else None


def country_field(context: PageContext, offset: int,
                  phone: extraction.VerifiedField | None = None) -> extraction.VerifiedField | None:
    """Country of the entity at text `offset`: its section heading, else the calling code
    of its phone (owner 06.10.2026: not the `/en-br/` of the page), else `<html lang>`."""
    section = extraction.section_at(list(context.sections), offset) if offset >= 0 else None
    if section is not None:
        head = section.heading
        return extraction.VerifiedField(section.country, head.quote, head.start, head.end, "text")
    called = norm.phone_country(phone.value) if phone is not None else None
    if phone is not None and called is not None:
        return extraction.VerifiedField(called, phone.quote, phone.start, phone.end, phone.locator)
    code = lang_country(context.lang)
    if code is None:
        return None
    return extraction.VerifiedField(code, context.lang.strip(), -1, -1, LOCATOR_LANG)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip()


def _is_department(label: str, own: tuple[str, ...], in_panel: bool) -> bool:
    """A generic heading (`Henkilosto`) names a department only inside a tab panel."""
    if len(label) > DEPARTMENT_MAX_LEN or discovery.label_country(label) is not None:
        return False
    words = {w.strip(",.") for w in label.lower().split()}
    if (not in_panel and _fold(label) in NOT_DEPARTMENTS) or words & LEGAL_WORDS:
        return False
    return label.casefold() not in {o.casefold() for o in own if o}


def department_field(
    text: str, group: str, contact: extraction.Contact, in_panel: bool = False
) -> extraction.VerifiedField | None:
    """The group heading as a department, quoted at its nearest place before the name."""
    label = norm.normalize_text(group)
    own = (contact.name.value, contact.title.value if contact.title else "")
    if not label or not _is_department(label, own, in_panel):
        return None
    at = text.rfind(label, 0, max(0, contact.name.start)) if contact.name.start >= 0 else -1
    if at >= 0:
        return extraction.VerifiedField(label, label, at, at + len(label), "text")
    span = find_span(text, label)
    if span is None:
        return None
    return extraction.VerifiedField(label, span.quote, span.start, span.end, "text")
