# discovery

Which URLs a walk may open and in which order (TZ_SELAIN section 8.2,
RULES K7/K8). Pure functions; the tables (social hosts, document suffixes,
contact and noise words) are in `repository.py`.

Entry point: `contract.py`.

| Function | Rule |
|---|---|
| `Candidate(index, kind, text, href, selector)` | one numbered element shown to the model; `kind` = `link` (navigated by URL) or `button` (clicked on the current page) |
| `approved_hosts_for(start, final)` | seed host + redirect target host, `www.` stripped (K7 bases `seed` and `redirect_from_seed`) |
| `is_allowed_url(url, hosts)` | http(s), host **equal** to an approved host (no suffix comparison: `katsa.sandvik.com` is not `sandvik.com`), not a social network, not a document (`.pdf`, `.docx`, images...) |
| `is_social_url(url)` | LinkedIn, Facebook, Instagram, X, YouTube, TikTok... never walked by our own code (K8) |
| `score_link(text, href)` | contact / team / staff / yhteystiedot / henkilosto / johto / myynti up, privacy / cookie / login / cart down, "next / show more" up |
| `rank_candidates(candidates, visited, hosts)` | allowed, unvisited (by normalised URL), de-duplicated links sorted by score, then every button |
| `normalize_url(url)` | lower-case scheme and host, no fragment, no default port, no trailing slash on paths |
| `page_key(url, text_sha256)` | state key = normalised URL + 16 hex of the content hash (section 8.5) |

Other bases of K7 (`linked_from_contact_section`, `business_id_match`,
`owner_known_url`) arrive with S2 jobs; a walk started from the panel knows
only the seed and its redirect.
