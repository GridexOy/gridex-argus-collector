"""Static tables of country matching (no I/O): names a country is labelled with.

Folded (lower case, no diacritics) names in English, the country's own
languages, Finnish, Swedish, German and French: the labels of country
accordions, tabs, dropdown options and site-version links. Two-letter codes
are matched separately and only as an upper-case label (`FI`, `SE`).
"""

from __future__ import annotations

COUNTRY_LABELS: dict[str, tuple[str, ...]] = {
    "FI": ("finland", "suomi", "finnland", "finlande", "finlandia", "finska"),
    "SE": ("sweden", "sverige", "ruotsi", "schweden", "suede", "svezia", "suecia"),
    "NO": ("norway", "norge", "norja", "norwegen", "norvege", "norvegia", "noruega"),
    "DK": ("denmark", "danmark", "tanska", "danemark", "dinamarca", "danimarca"),
    "IS": ("iceland", "island", "islanti", "islande", "islandia"),
    "EE": ("estonia", "eesti", "viro", "estland", "estonie"),
    "LV": ("latvia", "latvija", "lettland", "lettonie"),
    "LT": ("lithuania", "lietuva", "liettua", "litauen", "lituanie"),
    "DE": ("germany", "deutschland", "saksa", "tyskland", "allemagne", "germania", "alemania"),
    "AT": ("austria", "osterreich", "itavalta", "osterrike", "autriche"),
    "CH": ("switzerland", "schweiz", "sveitsi", "suisse", "svizzera", "suiza"),
    "NL": ("netherlands", "nederland", "alankomaat", "hollanti", "niederlande", "pays-bas",
           "holland", "the netherlands"),
    "BE": ("belgium", "belgie", "belgique", "belgien", "belgia"),
    "LU": ("luxembourg", "luxemburg", "luxemburgo"),
    "FR": ("france", "frankreich", "ranska", "frankrike", "francia"),
    "IT": ("italy", "italia", "italien", "italie"),
    "ES": ("spain", "espana", "espanja", "spanien", "espagne", "spagna"),
    "PT": ("portugal", "portugali", "portogallo"),
    "GB": ("united kingdom", "uk", "great britain", "england", "iso-britannia",
           "storbritannien", "grossbritannien", "royaume-uni", "regno unito"),
    "IE": ("ireland", "irlanti", "irland", "irlande", "eire"),
    "PL": ("poland", "polska", "puola", "polen", "pologne", "polonia"),
    "CZ": ("czech republic", "czechia", "cesko", "tsekki", "tschechien", "tjeckien"),
    "SK": ("slovakia", "slovensko", "slovakia", "slowakei"),
    "HU": ("hungary", "magyarorszag", "unkari", "ungarn", "hongrie"),
    "SI": ("slovenia", "slovenija", "slovenien"),
    "HR": ("croatia", "hrvatska", "kroatia", "kroatien"),
    "RS": ("serbia", "srbija", "serbien"),
    "RO": ("romania", "romania", "rumania", "rumanien", "roumanie"),
    "BG": ("bulgaria", "bulgarien", "bulgarie"),
    "GR": ("greece", "ellada", "kreikka", "griechenland", "grekland", "grece"),
    "TR": ("turkey", "turkiye", "turkki", "turkei", "turkiet", "turquie"),
    "UA": ("ukraine", "ukraina"),
    "US": ("united states", "usa", "united states of america", "yhdysvallat", "vereinigte staaten"),
    "CA": ("canada", "kanada"),
    "MX": ("mexico", "meksiko", "mexiko"),
    "BR": ("brazil", "brasil", "brasilia", "brasilien"),
    "CN": ("china", "kiina", "kina"),
    "JP": ("japan", "japani", "japon"),
    "KR": ("south korea", "korea", "etela-korea", "sydkorea"),
    "IN": ("india", "intia", "indien", "inde"),
    "SG": ("singapore", "singapur"),
    "AU": ("australia", "australien", "australie"),
    "NZ": ("new zealand", "uusi-seelanti", "neuseeland"),
    "ZA": ("south africa", "etela-afrikka", "sudafrika", "sydafrika"),
    "AE": ("united arab emirates", "uae", "arabiemiirikunnat"),
    "SA": ("saudi arabia", "saudi-arabia", "saudiarabien"),
    "IL": ("israel", "israele"),
}

# Two-letter labels that are country codes (upper case on the page: `FI`, `SE`).
COUNTRY_CODES: frozenset[str] = frozenset(COUNTRY_LABELS) | {"UK"}
CODE_ALIASES: dict[str, str] = {"UK": "GB"}

# `fi.example.com`: a sub-domain that names a country version of the site.
SUBDOMAIN_COUNTRIES: dict[str, str] = {
    "fi": "FI", "se": "SE", "no": "NO", "dk": "DK", "ee": "EE", "de": "DE", "at": "AT",
    "ch": "CH", "nl": "NL", "be": "BE", "fr": "FR", "it": "IT", "es": "ES", "pl": "PL",
    "uk": "GB", "lt": "LT", "lv": "LV", "is": "IS",
}

# Words of a label that are not part of the country name (`Finland office`).
LABEL_NOISE = ("office", "offices", "toimisto", "kontor", "buro", "contact", "contacts",
               "yhteystiedot", "kontakt", "sales", "myynti", "site", "website")

# Department tabs and accordions: sales and marketing first, support functions last.
DEPARTMENT_FIRST: tuple[str, ...] = (
    "myynti", "sales", "markkinointi", "marketing", "vienti", "export", "forsaljning",
    "salj", "marknad", "vertrieb", "verkauf", "asiakkuudet", "key account",
)
DEPARTMENT_LAST: tuple[str, ...] = (
    "hallinto", "administration", "talous", "finance", "henkilosto", "hr", "varasto",
    "warehouse", "lager", "logistiikka", "logistics", "it", "laskutus", "invoicing",
    "kirjanpito", "accounting", "tuotanto", "production",
)
