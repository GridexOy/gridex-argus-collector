# ui

The collector panel: one tkinter window, light theme, Finnish strings from
`collector/messages/fi.json` (TZ_SELAIN section 5.1, section 7: tkinter, no
web server). Entry point: `contract.run_panel()` / `python -m argus_collector.ui`.

| File | Role |
|---|---|
| `repository.py` | loads the message catalogue; `Messages.t(key, **params)` raises on a missing key |
| `service.py` | pure `build_props(...)`: facts from `runtime` and `diagnostics` in, `PanelProps` (strings + flags) out |
| `walk_lines.py` | pure: `CollectProps`, walk events -> Finnish status lines and table rows |
| `view.py` / `view_collect.py` | tkinter widgets rendered from props only; `render(props)` re-applies them; the Keruu block appends rows live |
| `app.py` / `app_walk.py` | data hooks: version/STOP from `runtime`, diagnostics in a thread, work browser as a detached process, the walk in its own thread (events reach tkinter only through `ui_queue`) |

Blocks and states:

- bottom-left: `cv0.4.1.0 (3.10.2026 klo 14.32) <commit>` from `VERSION` + `build.json`; a mismatch is shown in red.
- Yhteys: `Ei yhteyttä` (no server connection exists before S1).
- Keruu: field "Yrityksen verkkosivu", "Käynnistä" (live only when the model is listed, Chrome is available and no STOP file exists; the hint line says why otherwise), "Pysäytä" (live while a walk runs), "Keskeytä" and both autostart settings still disabled (S5); status line (page n/budget, step, model error, done / stopped / error in colour); "Löydetty: N yhteystietoa"; table Nimi · Titteli · Puhelin · Sähköposti · Lähde filled while walking, double-click opens the source URL in the default browser.
- Resurssit: lines from `diagnostics` (OS, Chrome, model + its endpoint/detail line, disk, memory, NVIDIA); errors in red, `Tarkistetaan…` while collecting; re-collected after every walk (Ollama loads the model on first use, so `Malli` turns to GPU after the first walk).
- "Avaa työselain": the launcher on the test site (disabled while a walk runs: both use the same Chrome profile).
- STOP file in the repo root or in the user data dir: red banner with the paths; a running walk stops at its next step.

Tests (`tests/`) build props without a display and render the real window
under Xvfb when no display is present (skipped when neither exists).
