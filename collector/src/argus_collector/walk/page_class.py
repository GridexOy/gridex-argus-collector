"""What kind of page this is: `contact`, `form` or `other` (K12, TZ v4.0 4.2 p. 5).

The ladder needs the difference between a contact page and a page that only offers a
contact form behind a captcha. The second holds no people and no channels, and a
captcha means the walk will not get past it either: it is classed `form`, is never
counted as the contact page the ladder was looking for, and the walk goes on down the
ladder instead of spending its pages there. The class is also what the panel shows in
Jono (`Vaihe: yhteystiedot-sivu 2/8 · 00:41`).
"""

from __future__ import annotations

from argus_collector.discovery import contract as discovery
from argus_collector.extraction import contract as extraction

CONTACT, FORM, OTHER = "contact", "form", "other"
CAPTCHA_MARKS = ("recaptcha", "hcaptcha", "cf-turnstile", "turnstile", "captcha",
                 "data-sitekey")
MIN_CHANNELS = 2


def _captcha(html: str) -> bool:
    low = html.casefold()
    return any(mark in low for mark in CAPTCHA_MARKS)


def classify(url: str, title: str, html: str, channels: list[extraction.Channel],
             people: int) -> str:
    """`contact` when the page names itself one or prints personal channels; `form` when
    it is a captcha-guarded form with nobody and nothing to call; else `other`."""
    printed = [c for c in channels if c.kind in ("phone", "email")]
    if people or len(printed) >= MIN_CHANNELS:
        return CONTACT
    named = discovery.contact_link(title, url)
    if not printed and _captcha(html) and "<form" in html.casefold():
        return FORM
    return CONTACT if named else OTHER
