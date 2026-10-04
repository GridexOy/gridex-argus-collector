# test_site

Reproducible local fixture site for the collector (TZ_SELAIN section 12.2).
Static HTML served by the Python standard library, no dependencies.

```
python -m test_site.server --port 8765      # http://127.0.0.1:8765/ + http://<label>.localhost:8765/
python -m test_site.companies --port 8765   # the fixture companies as batch input (companies.json)
```

`127.0.0.1` serves `site/` (fixture_oy); every other company is a virtual
host `<label>.localhost` served from `sites/<label>/` (Chrome resolves
`*.localhost` to loopback by itself and never sends it through a proxy).

`server.start(port)` starts the same server in a daemon thread for tests and
for the panel button "Avaa työselain" (see `argus_collector.browser`).
Port 0 picks a free port; the default is `test_site.port` in `config.yaml`.

## Fixtures

| Fixture | Pages | Gold |
|---|---|---|
| `fixture_oy` | `index.html` (home, footer with company phone/email, JSON-LD Organization), `contact.html` (three people with `tel:`/`mailto:` links), `team.html` (two people whose email/phone appear only after the button "Näytä yhteystiedot"; link "Seuraava sivu"), `team-2.html` (one person with `jukka.laine (at) fixture.example` and a plain-text phone, one with links; a LinkedIn link the walk must not open) | `gold/fixture_oy.json` |
| `nordtec` (0.4.3.0) | Swedish company, English root with `Svenska` / `Suomi` switch, `fi/yhteystiedot.html` = Finland office (2 people, `puh.` in text), HQ contacts in English and Swedish, Norway office line, `Vaihde` footer: with priority_countries FI the Finnish version and office come first | `gold/nordtec.json` |
| `vogel` (0.4.3.0) | German company without an office in Finland: German root (`lang="de"`, national numbers `0711 ...`), `export.html` (Exportleiter Nordeuropa), `en/contact.html` (Area Sales Manager Nordics, Marketing Manager International), a French page that must come last | `gold/vogel.json` |
| `katsa` (0.4.3.0) | seed `katsa-oy.localhost` redirects (302) to `katsa-group.localhost`, which is not in its approved_hosts: gap `domain_ownership_unresolved`, nothing sent | `gold/katsa.json` |

The gold file lists every record the collector must find: company fields and
persons with `name`, `title`, `email`, `phone` (E.164), the page they come
from and `how` the page shows them: `link` (`tel:`/`mailto:` in the html),
`button` (built by JS from `data-user`/`data-domain`/`data-phone` after the
button) or `text` (obfuscated `email_text`, plain `phone_text`).
`tests/test_server.py` checks each form in the served HTML, so page and gold
cannot drift apart; `argus_collector.walk` tests walk the whole site.

## Scope by stage

0.4.1.0 ships one company with plain HTML, footer, JSON-LD, a reveal
button, pagination and an obfuscated address; 0.4.3.0 adds the country
focus, a foreign company and a seed leaving its approved host. The rest of
section 12.2 (JS catalogue with "show more", department filters, duplicate
names and shared phone, redirect between approved hosts, iframe/shadow
DOM, PDF/vCard/OCR for M2, captcha/timeout/infinite pagination, injected
instructions) comes with the passes that use them, each with a gold file.
