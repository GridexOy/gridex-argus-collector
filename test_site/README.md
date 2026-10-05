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

Gold files list every record the collector must find (E.164 `phone`, the
page's raw `phone_text`, `source_page`; `how` = `link` / `button` / `text`
for fixture_oy) and what it must leave out (`excluded`, `forbidden_values`).
`tests/` check every gold value against the served HTML, so page and gold
cannot drift apart; `argus_collector.walk` tests walk the sites.

Still to come from section 12.2, each with its gold file when a pass uses it:
JS catalogue with "show more", duplicate names and shared phone, redirect
between approved hosts, iframe/shadow DOM, PDF/vCard/OCR for M2, captcha,
timeout, infinite pagination, injected instructions.
