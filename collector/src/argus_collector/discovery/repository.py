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
    "kontakte": 9,
    "vertrieb": 6,
    "ansprechpartner": 8,
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

# Exhibition-country focus (scope.priority_countries): words naming the country
# or its main cities in a link text or URL path (English, own language, Finnish,
# German) and the English country name used in the model prompt.
COUNTRY_WORDS: dict[str, tuple[str, ...]] = {
    "FI": ("finland", "suomi", "suomen", "suomessa", "finnland", "finlande", "finska",
           "helsinki", "espoo", "vantaa", "tampere", "turku", "oulu", "jyvaskyla"),
    "SE": ("sweden", "sverige", "ruotsi", "schweden", "stockholm", "goteborg", "malmo"),
    "NO": ("norway", "norge", "norja", "norwegen", "oslo", "bergen"),
    "DK": ("denmark", "danmark", "tanska", "danemark", "copenhagen", "kobenhavn"),
    "EE": ("estonia", "eesti", "viro", "estland", "tallinn"),
    "DE": ("germany", "deutschland", "saksa", "allemagne"),
}
COUNTRY_NAMES: dict[str, str] = {
    "FI": "Finland", "SE": "Sweden", "NO": "Norway", "DK": "Denmark", "EE": "Estonia",
    "DE": "Germany", "AT": "Austria", "CH": "Switzerland", "NL": "Netherlands",
    "PL": "Poland", "GB": "United Kingdom", "FR": "France", "IT": "Italy", "ES": "Spain",
}

# A language-switch link names its language (`Suomi`, `English`, `FI`).
LANGUAGE_NAMES: dict[str, tuple[str, ...]] = {
    "fi": ("suomi", "suomeksi", "finnish", "fi"),
    "sv": ("svenska", "pa svenska", "swedish", "sv"),
    "en": ("english", "in english", "en"),
    "de": ("deutsch", "german", "de"),
    "no": ("norsk", "norwegian", "no", "nb"),
    "da": ("dansk", "danish", "da", "dk"),
    "et": ("eesti", "estonian", "et", "ee"),
    "fr": ("francais", "french", "fr"),
    "es": ("espanol", "spanish", "es"),
    "it": ("italiano", "italian", "it"),
    "pl": ("polski", "polish", "pl"),
    "nl": ("nederlands", "dutch", "nl"),
}

# Without an office in the exhibition country the people to reach are in
# export / Nordic / international sales and marketing (owner, 04.10.2026).
EXPORT_WORDS: dict[str, int] = {
    "export": 7, "exports": 7, "vienti": 7, "nordic": 7, "nordics": 7, "nordeuropa": 7,
    "scandinavia": 7, "skandinavien": 7, "skandinavia": 7, "pohjoismaat": 7,
    "international": 7, "internationell": 7, "global": 4, "overseas": 6, "ausland": 6,
    "exportvertrieb": 7, "area": 2, "regional": 3, "marketing": 4, "markkinointi": 4,
}
FOCUS_COUNTRY_BONUS = 12
FOCUS_FIRST_LANGUAGE_BONUS = 12
FOCUS_OTHER_LANGUAGE_BONUS = 4
FOCUS_FOREIGN_LANGUAGE_PENALTY = -8
FOCUS_EXPORT_CAP = 10
