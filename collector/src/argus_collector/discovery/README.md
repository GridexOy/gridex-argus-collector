# discovery

Which URLs a walk may open and in which order (TZ_SELAIN section 8.2,
RULES K7/K8). Pure functions; the tables (social hosts, document suffixes,
contact and noise words) are in `repository.py`.

Entry point: `contract.py`.

| Function | Rule |
|---|---|
| `Candidate(index, kind, text, href, selector, role, state, options)` | one numbered element; `kind` = `link` (navigated by URL), `button` (clicked) or `select` (dropdown, `options`); `role` `tab` / `expand`, `state` `on` when selected / expanded |
| `approved_hosts_for(start, final)` | seed host + redirect target host, `www.` stripped (K7 bases `seed` and `redirect_from_seed`) |
| `is_allowed_url(url, hosts)` | http(s), host **equal** to an approved host (no suffix comparison: `katsa.sandvik.com` is not `sandvik.com`), not a social network, not a document (`.pdf`, `.docx`, images...) |
| `is_social_url(url)` | LinkedIn, Facebook, Instagram, X, YouTube, TikTok... never walked by our own code (K8) |
| `score_link(text, href)` | contact / team / staff / yhteystiedot / henkilosto / johto / myynti up, privacy / cookie / login / cart down, "next / show more" up |
| `rank_candidates(candidates, visited, hosts)` | allowed, unvisited (by normalised URL), de-duplicated links sorted by score, then every button |
| `normalize_url(url)` | lower-case scheme and host, no fragment, no default port, no trailing slash on paths |
| `page_key(url, text_sha256)` | state key = normalised URL + 16 hex of the content hash (section 8.5) |

| `make_focus(countries, languages)` / `focus_brief(focus)` | 0.4.3.0 (`focus.py`, owner 04.10.2026): scope.priority_countries / priority_languages. Links get +12 for the first language (`Suomi`, `/fi/`, `?lang=fi`) and for the exhibition country or its cities (`Finland office`), +4 for other priority languages, -8 for a third language; export / Nordic / international sales and marketing words up to +10 (a company without an office there). The brief tells the model the same order |

| `label_country` / `url_country` / `link_country` / `is_local_seed` / `country_members` / `strong_link` / `department_rank` | 0.4.4.0 (`countries.py`, tables `country_names.py`, owner 05.10.2026): a label naming a country (`Finland`, `Suomi`, `FI`), a URL's country version (ccTLD, `fi.` host, `/fi-fi/`, `/fi/`), a page listing >= 3 countries, the seed already being the exhibition-country version (then other country versions are walked after it), links the model may not skip, sales / marketing tabs first |

0.4.8.0 (Beckhoff): `is_worldwide` (`Beckhoff Worldwide`, `Global presence`, `Weltweit`:
the country list is behind it), `foreign_country` (another country by its label or
locale path, never by the domain), `locale_segment`, `contact_link` (contact words
without the country bonus: a rule may follow it without the model).

A job walk takes its hosts from the job's `approved_hosts` (K7 ed. 02:
basis `seed`; `redirect_from_seed` waits for the owner's "ok"); a walk
started from the panel knows only the seed and its redirect.
