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
| `fixture_oy` | `index.html` (home, footer with company phone/email), `contact.html` (three people with title, email, phone; office address) | `gold/fixture_oy.json` |

The gold file lists every record the collector must find: company fields and
persons with `name`, `title`, `email`, `phone` (E.164 as in the `tel:` href)
and the page they come from. `tests/test_server.py` checks that every gold
value is present in the served HTML, so page and gold cannot drift apart.

## Scope by stage

S0 ships only the minimal set above (one company, plain HTML, footer).
The remaining fixtures of section 12.2 (JSON-LD, JS catalogue with
pagination and "show more", accordion/email reveal, department filters,
duplicate names and shared phone, redirect between approved hosts,
iframe/shadow DOM, PDF/vCard/OCR for M2, captcha/timeout/infinite
pagination, injected instructions, phone on a host outside
`approved_hosts`) are added in S2-S3 together with the passes that use them,
each with its own gold file.
