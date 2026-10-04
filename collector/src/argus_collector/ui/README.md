# ui

The collector panel: one tkinter window, light theme, Finnish strings from
`collector/messages/fi.json` (TZ_SELAIN section 5.1, section 7: tkinter, no
web server). Entry point: `contract.run_panel()` / `python -m argus_collector.ui`.

| File | Role |
|---|---|
| `repository.py` | loads the message catalogue; `Messages.t(key, **params)` raises on a missing key |
| `service.py` | pure `build_props(...)`: facts from `runtime` and `diagnostics` in, `PanelProps` (strings + flags) out |
| `walk_lines.py` | pure: `CollectProps`, walk events -> Finnish status lines and table rows |
| `connection_lines.py` | pure: `ConnectionProps`, `ConnectionState` -> Yhteys block strings |
| `queue_lines.py` | pure: Jono rows (Yritys · Vaihe · Henkilöt · Kanavat · Lähteet · Tila; an ARGUS rejection in words) and the Lähetys line |
| `view*.py` | tkinter widgets rendered from props only (`view_queue.py`: Jono, Lähetys) |
| `app.py` / `app_walk.py` / `app_connection.py` / `app_collect.py` | data hooks: diagnostics, work browser, the local test walk, the heartbeat loop (leases, command acks from `scheduler`), the `scheduler.Collector` (events reach tkinter only through `ui_queue`) |

Blocks and states:

- bottom-left: `cv0.4.1.0 (3.10.2026 klo 14.32) <commit>` from `VERSION` + `build.json`; a mismatch is shown in red.
- Yhteys (ARGUS20_TZ_TANDEM.md pair A1): address (default `config.yaml` `argus.base_url`), worker_id and token fields (token write-only, never pre-filled; stored via `worker_auth`), "Testaa yhteys" -> one heartbeat call through `api_client`; states `Ei yhteyttä` / `Tarkistetaan…` / `Yhdistetty` / `Tunnus hylätty` / `Ei verkkoa: <detail>` (the time of the last answered heartbeat stays shown); a saved worker_id + token re-sends a heartbeat automatically every 30 s while the panel is open.
- Keruu (0.4.3.0, TZ_TANDEM A2/A3): "Käynnistä" collects ARGUS jobs (live with a listed model, Chrome, a working connection, no STOP; the hint says why not), "Pysäytä" stops collecting and the local test (the outbox keeps sending), "Keskeytä" and both autostart settings still disabled (S5); field "Yrityksen verkkosivu" + "Testaa paikallisesti" (or Enter): one local walk, nothing sent; status line (page n/budget, step, model error, done / stopped / error in colour; `Keruu valmis` after each ARGUS job too); "Löydetty: N yhteystietoa"; table Nimi · Titteli · Puhelin · Sähköposti · Lähde filled while walking, double-click opens the source URL in the default browser.
- Jono: `Ladataan…` / `Jonon lataus epäonnistui` / `Ei tehtäviä` / the table; Lähetys: `Odottaa lähetystä: N · Lähetysvirhe: N · p95 (1 min)` and `Lähetetty` / `Lähetetään` / `Ei verkkoa` (also with an empty outbox when the heartbeat gets no answer) / `Lähetys epäonnistui` (red); both re-read the local SQLite every second.
- Resurssit: lines from `diagnostics` (OS, Chrome, model + its endpoint/detail line, disk, memory, NVIDIA); errors in red, `Tarkistetaan…` while collecting; re-collected after every walk (Ollama loads the model on first use, so `Malli` turns to GPU after the first walk).
- "Avaa työselain": the launcher on the test site (disabled while walking or collecting: one Chrome profile).
- STOP file in the repo root or in the user data dir: red banner with the paths; a running walk stops at its next step.

Tests (`tests/`) build props without a display and render the real window
under Xvfb when no display is present (skipped when neither exists).
