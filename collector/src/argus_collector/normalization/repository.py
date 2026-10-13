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

# `@` written as a word is only read as one when the rest still looks like an address:
# the domain carries no spaces and ends in a letters-only top level (owner 13.10.2026).
# Without that, ordinary prose became addresses on live pages - "look at it. Going" read
# as look@it.going, "Ampeerin (A) virran. Tehohan" as ampeerin@virran.tehohan, and ARGUS
# refused them as `value_not_in_quote`.
AT_SIGN = r"@"
AT_WORD = r"(?:\(\s*(?:at|a|ät)\s*\)|\[\s*(?:at|a|ät)\s*\]|\{\s*at\s*\}|\s+(?:at|ät)\s+)"
AT_PATTERN = rf"(?:{AT_SIGN}|{AT_WORD})"
DOT_PATTERN = r"(?:\.|\(\s*(?:dot|piste)\s*\)|\[\s*(?:dot|piste)\s*\]|\s+(?:dot|piste)\s+)"
LOCAL_PART = r"[A-Za-z0-9._%+\-]+"
DOMAIN_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?"
TOP_LEVEL = r"[A-Za-z]{2,24}"
SPACED_DOMAIN = (rf"{DOMAIN_LABEL}(?:\s*{DOT_PATTERN}\s*{DOMAIN_LABEL})*"
                 rf"\s*{DOT_PATTERN}\s*{TOP_LEVEL}")
# A dot spelled as a word binds its labels even with spaces; a bare dot must have
# none, or prose like "it. Going" reads as a domain (owner 13.10.2026).
DOT_TIGHT = (r"(?:\.|\s*[(\[]\s*(?:dot|piste)\s*[)\]]\s*"
             r"|\s+(?:dot|piste)\s+)")
TIGHT_DOMAIN = (rf"{DOMAIN_LABEL}(?:{DOT_TIGHT}{DOMAIN_LABEL})*"
                rf"{DOT_TIGHT}{TOP_LEVEL}")

EMAIL_FIND_RE = re.compile(
    rf"{LOCAL_PART}\s*{AT_SIGN}\s*{SPACED_DOMAIN}"
    rf"|{LOCAL_PART}\s*{AT_WORD}\s*{TIGHT_DOMAIN}",
    re.IGNORECASE,
)
# A word-spelled `@` counts only with a tight domain around it: no spaces
# inside the domain and a letters-only top level (owner 13.10.2026).
EMAIL_SPELLED_RE = re.compile(
    rf"{LOCAL_PART}\s*{AT_WORD}\s*{TIGHT_DOMAIN}(?![A-Za-z0-9.-])",
    re.IGNORECASE,
)
# The top level of a real address is letters: `balance@9.6` is a measurement, not a
# mailbox (owner 13.10.2026).
EMAIL_VALID_RE = re.compile(rf"^{LOCAL_PART}@{DOMAIN_LABEL}(?:\.{DOMAIN_LABEL})*\.{TOP_LEVEL}$")

# Phone-looking runs: optional +/00, digits with spaces, dashes, dots, parentheses.
PHONE_FIND_RE = re.compile(r"(?<![\w/])(?:\+|00)?\(?\d[\d\s\-.()]{5,}\d(?![\w/])")
EXTENSION_RE = re.compile(r"(?:ext\.?|x|/)\s*\d+\s*$", re.IGNORECASE)
NON_DIGITS = re.compile(r"\D+")
WHITESPACE = re.compile(r"\s+")

# A line that cannot be a person name: digits, @, too long, too short.
NAME_BAD_RE = re.compile(r"[\d@/\\|<>{}\[\]]")
NAME_MAX_LEN = 80
