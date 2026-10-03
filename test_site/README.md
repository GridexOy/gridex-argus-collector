# test_site

Reproducible local fixture site for the collector (TZ_SELAIN section 12.2).
Static HTML served by the Python standard library, no dependencies.

```
python -m test_site.server --port 8765      # http://127.0.0.1:8765/
```

`server.start(port)` starts the same server in a daemon thread for tests and
for the panel button "Avaa työselain" (see `argus_collector.browser`).
Port 0 picks a free port; the default is `test_site.port` in `config.yaml`.

## Fixtures

| Fixture | Pages | Gold |
|---|---|---|
| `fixture_oy` | `index.html` (home, footer with company phone/email, JSON-LD Organization), `contact.html` (three people with `tel:`/`mailto:` links), `team.html` (two people whose email/phone appear only after the button "Näytä yhteystiedot"; link "Seuraava sivu"), `team-2.html` (one person with `jukka.laine (at) fixture.example` and a plain-text phone, one with links; a LinkedIn link the walk must not open) | `gold/fixture_oy.json` |

The gold file lists every record the collector must find: company fields and
persons with `name`, `title`, `email`, `phone` (E.164), the page they come
from and `how` the page shows them: `link` (`tel:`/`mailto:` in the html),
`button` (built by JS from `data-user`/`data-domain`/`data-phone` after the
button) or `text` (obfuscated `email_text`, plain `phone_text`).
`tests/test_server.py` checks each form in the served HTML, so page and gold
cannot drift apart; `argus_collector.walk` tests walk the whole site.

## Scope by stage

0.4.1.0 ships one company with plain HTML, footer, JSON-LD, a reveal
button, pagination and an obfuscated address. The remaining fixtures of
section 12.2 (JS catalogue with "show more", department filters,
duplicate names and shared phone, redirect between approved hosts,
iframe/shadow DOM, PDF/vCard/OCR for M2, captcha/timeout/infinite
pagination, injected instructions, phone on a host outside
`approved_hosts`) are added in S2-S3 together with the passes that use them,
each with its own gold file.
