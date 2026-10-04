"""Static tables of the normalization module (no I/O): regions and patterns."""

from __future__ import annotations

import re

# Country calling codes by region; only regions the collector may assume.
REGION_CODES: dict[str, str] = {
    "FI": "358", "SE": "46", "NO": "47", "DK": "45", "EE": "372", "IS": "354",
    "DE": "49", "AT": "43", "CH": "41", "NL": "31", "BE": "32", "FR": "33",
    "IT": "39", "ES": "34", "PL": "48", "GB": "44", "LT": "370", "LV": "371",
}

# Country-code top-level domains that fix the national phone context of a page.
TLD_REGIONS: dict[str, str] = {
    "fi": "FI", "se": "SE", "no": "NO", "dk": "DK", "ee": "EE", "is": "IS",
    "de": "DE", "at": "AT", "ch": "CH", "nl": "NL", "be": "BE", "fr": "FR",
    "it": "IT", "es": "ES", "pl": "PL", "uk": "GB", "lt": "LT", "lv": "LV",
}

# Page language -> country when the page names no region (`de` -> DE). English
# names no country; Swedish defaults to Sweden (a Finnish site in Swedish has
# a .fi domain or an `sv-FI` tag, both checked first).
LANGUAGE_REGIONS: dict[str, str] = {
    "fi": "FI", "sv": "SE", "nb": "NO", "nn": "NO", "no": "NO", "da": "DK",
    "et": "EE", "is": "IS", "de": "DE", "nl": "NL", "fr": "FR", "it": "IT",
    "es": "ES", "pl": "PL", "lt": "LT", "lv": "LV",
}
LOCALE_RE = re.compile(r"^([a-z]{2})(?:[-_]([a-z]{2}))?$", re.IGNORECASE)

# Minimum/maximum digits of a national significant number per E.164.
MIN_DIGITS = 7
MAX_DIGITS = 15

# Obfuscation spellings of "@" and "." seen on company sites.
AT_WORDS = ("(at)", "[at]", "{at}", " at ", "(a)", "[a]", "(ät)", "[ät]", " ät ", "&#64;")
DOT_WORDS = ("(dot)", "[dot]", "{dot}", " dot ", "(piste)", "[piste]", " piste ")

AT_PATTERN = r"(?:@|\(\s*(?:at|a|ät)\s*\)|\[\s*(?:at|a|ät)\s*\]|\{\s*at\s*\}|\s+(?:at|ät)\s+)"
DOT_PATTERN = r"(?:\.|\(\s*(?:dot|piste)\s*\)|\[\s*(?:dot|piste)\s*\]|\s+(?:dot|piste)\s+)"
LOCAL_PART = r"[A-Za-z0-9._%+\-]+"
DOMAIN_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?"

EMAIL_FIND_RE = re.compile(
    rf"{LOCAL_PART}\s*{AT_PATTERN}\s*{DOMAIN_LABEL}(?:\s*{DOT_PATTERN}\s*{DOMAIN_LABEL})+",
    re.IGNORECASE,
)
EMAIL_VALID_RE = re.compile(rf"^{LOCAL_PART}@{DOMAIN_LABEL}(?:\.{DOMAIN_LABEL})+$")

# Phone-looking runs: optional +/00, digits with spaces, dashes, dots, parentheses.
PHONE_FIND_RE = re.compile(r"(?<![\w/])(?:\+|00)?\(?\d[\d\s\-.()]{5,}\d(?![\w/])")
EXTENSION_RE = re.compile(r"(?:ext\.?|x|/)\s*\d+\s*$", re.IGNORECASE)
NON_DIGITS = re.compile(r"\D+")
WHITESPACE = re.compile(r"\s+")

# A line that cannot be a person name: digits, @, too long, too short.
NAME_BAD_RE = re.compile(r"[\d@/\\|<>{}\[\]]")
NAME_MAX_LEN = 80
