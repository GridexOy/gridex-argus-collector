"""Static tables of discovery (no I/O): social hosts, document suffixes, words."""

from __future__ import annotations

# K8: social networks and LinkedIn are never walked by our own code.
SOCIAL_HOSTS: frozenset[str] = frozenset(
    {
        "linkedin.com",
        "facebook.com",
        "fb.com",
        "instagram.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "youtu.be",
        "tiktok.com",
        "pinterest.com",
        "threads.net",
        "vk.com",
        "snapchat.com",
        "whatsapp.com",
        "t.me",
        "telegram.org",
    }
)

# Documents are M2 (`documents` module); a walk does not open them.
DOCUMENT_SUFFIXES = (
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".csv",
    ".zip",
    ".vcf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".mp4",
)

# Words that make a link worth opening first (TZ section 8.2), with weights.
CONTACT_WORDS: dict[str, int] = {
    "yhteystiedot": 10,
    "yhteys": 8,
    "henkilosto": 9,
    "henkilöstö": 9,
    "henkilokunta": 9,
    "henkilökunta": 9,
    "tiimi": 7,
    "johto": 7,
    "myynti": 7,
    "contact": 10,
    "contacts": 10,
    "team": 8,
    "staff": 8,
    "people": 8,
    "personnel": 8,
    "management": 6,
    "sales": 6,
    "support": 4,
    "office": 4,
    "offices": 4,
    "locations": 4,
    "about": 3,
    "kontakt": 9,
    "personal": 6,
    "medarbetare": 8,
}

# Words that push a link down (not where people are listed).
NOISE_WORDS: dict[str, int] = {
    "privacy": -8,
    "tietosuoja": -8,
    "cookie": -8,
    "evaste": -8,
    "login": -6,
    "kirjaudu": -6,
    "cart": -6,
    "ostoskori": -6,
    "news": -2,
    "uutiset": -2,
    "blog": -2,
    "careers": -1,
    "rekry": -1,
    "logout": -9,
    "search": -3,
}

NEXT_WORDS = ("seuraava", "next", "lisää", "lisaa", "more", "näytä", "nayta", "show", "»", ">")
