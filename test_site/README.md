# test_site

Reproducible local fixture site for the collector (TZ_SELAIN section 12.2).
Static HTML served by the Python standard library, no dependencies.

```
python -m test_site.server --port 8765 [--variant departed|challenge-stuck]
python -m test_site.companies --port 8765   # the fixture companies as batch input (companies.json)
```

`127.0.0.1` serves `site/` (fixture_oy); every other company is a virtual
host `<label>.localhost` served from `sites/<label>/` (Chrome resolves
`*.localhost` to loopback by itself and never sends it through a proxy).
`server.start(port=0, variant=None)` runs the same server in a daemon thread
for tests and for the panel button "Avaa työselain"; the default port is
`test_site.port` in `config.yaml`. Folders are never listed (404).

Server features (`pages.py`):
- **Port placeholder**: `__PORT__` in an `.html` page becomes the port of the
  request (Host header, else the server's), for links between two hosts.
- **Variants**: `variants/<name>/<label>/<path>` (label `site` = 127.0.0.1)
  replaces that one file. `departed`: `team.html` without Pekka Salo (a re-run
  must report him `not_seen_in_checked_scope`).
- **Bot check**: `ledvance.localhost/fi-fi/*` without cookie
  `fixture_waf=passed` answers 200 with `templates/challenge.html` ("Just a
  moment...", `#challenge-running`); its script sets the cookie after 3 s and
  reloads. `challenge-stuck`: the script sets no cookie and the server ignores
  one, so the interstitial never clears (it keeps reloading).

| Fixture | Case | Gold |
|---|---|---|
| `fixture_oy` | home with footer and JSON-LD; `contact.html` three people with links; `team.html` two people behind "Näytä yhteystiedot", "Seuraava sivu"; `team-2.html` obfuscated email, plain phone, LinkedIn link never walked | `fixture_oy.json` |
| `nordtec` | Swedish company, Finland office in `fi/`: with priority_countries FI the Finnish version and office first | `nordtec.json` |
| `vogel` | German company without a Finland office: export / Nordic / international people first, French page last | `vogel.json` |
| `katsa` | seed redirects (302) off its approved host: gap `domain_ownership_unresolved`, nothing sent | `katsa.json` |
| `ledvance` | global `en-int/company/contact/`: accordion of 11 countries, open only Finland (office, switchboard, email, not the fax), follow `/fi-fi/` (bot check) for 6 people; `contact-select/` the same as a dropdown | `ledvance.json` |
| `malux` | seed `/fi/`; `fi/yhteystiedot/` 4 department tabs (only the first open), every tab walked, sales/marketing first; sister site `malux-se.localhost/sv/` after, people with country SE | `malux.json` |
| `beckhoff` | seed `en-en/`, the same header and footer menus on every en-en page; `en-en/company/global-presence/` has 2 tabs and Germany is open on load (HQ, 8 sales offices, link `/de-de/`; the trap of 05.10.2026). Correct path: tab "Beckhoff Worldwide", then open only Finland in the 19-country accordion (office with switchboard, email and fax), then the local site `/fi-fi/`, where `yhteystiedot/` has 6 people under department headings and `yritys/johto/` 2 managers as cards and as JSON-LD `Person`. `/de-de/` is never visited | `beckhoff.json` |
| `ellego` | seed `/` (owner case 05.10.2026: cards visible on the first contact page, nobody extracted). Every page has the same WordPress-like mega menu rendered open, so on `contact/` more than 9000 characters of menu text come before the first card; there 40 people under six h2 groups ("Sales & Marketing" first, the five owner-named people on top), name, title and phone on every card, email on every second; above them a filter bar of plain buttons (All + one per group, no role, no aria) that hides the other groups, all open on load. Every card is read on `contact/` before any click or navigation, and the filters are not clicked in a circle | `ellego.json` |
| `reimax` | seed `/` (owner case 06.10.2026, Reimax: the page states the address pattern). `contact/` says "Our e-mail addresses are the following: firstname.lastname@reimax.example" above 14 cards with name, title and phone and no email; the footer has the switchboard and `info@`. The rules read all 14; every one gets the address of the stated pattern, unconfirmed (`inferred`, oletettu) with the pattern line as its quote; the pattern is the company's `email_pattern`, never a channel; no model call on the page; the walk ends at the goal on `contact/` | `reimax.json` |
| `elkris` + `industryx` | owner case 06.10.2026 (Elkris/Reimax, K7): the company site links an event page on another host, `industryx.localhost/puhujat/`, with two speakers (name, title, phone, email). Approved only as `linked_from_contact_section`, that page is a source; nobody and no channel is read from it; without the K7 domains the same page gives both | `elkris.json` |
| `blaklader` | owner case 06.10.2026 (Blåkläder: «Löydetty: 44» for 22 people): `yhteystiedot/` has 22 cards whose names the HTML writes in mixed case and the CSS shows in capitals (`text-transform`); the 7 sales people appear again on `myynti/`. 22 person rows reach ARGUS, each name as written | `blaklader.json` |
| `gavazzi` | owner case 06.10.2026 (Carlo Gavazzi went to `/en-br/`): seed `/en-br/` (lang `en-BR`, two people of the Brazilian office), no hreflang and no switcher; `/fi/` answers 404, `/en-fi/` is the Finnish version with three people. The walk goes to `/en-fi/` before reading anything | `gavazzi.json` |

Gold files list every record the collector must find (E.164 `phone`, the
page's raw `phone_text`, `source_page`; `how` = `link` / `button` / `text`
for fixture_oy) and what it must leave out (`excluded`, `forbidden_values`).
`tests/` check every gold value against the served HTML, so page and gold
cannot drift apart; `argus_collector.walk` tests walk the sites.

Still to come from section 12.2, each with its gold file when a pass uses it:
JS catalogue with "show more", duplicate names and shared phone, redirect
between approved hosts, iframe/shadow DOM, PDF/vCard/OCR for M2, captcha,
timeout, infinite pagination, injected instructions.
