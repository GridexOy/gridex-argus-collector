# ui

The collector panel: one tkinter window, light theme, Finnish strings from
`collector/messages/fi.json` (TZ_SELAIN section 5.1, section 7: tkinter, no
web server). Entry point: `contract.run_panel()` / `python -m argus_collector.ui`.

| File | Role |
|---|---|
| `repository.py` | loads the message catalogue; `Messages.t(key, **params)` raises on a missing key |
| `service.py` | pure `build_props(...)`: facts from `runtime` and `diagnostics` in, `PanelProps` (strings + flags) out |
| `view.py` | tkinter widgets rendered from props only; `render(props)` re-applies them |
| `app.py` | data hooks: version/STOP from `runtime`, diagnostics in a thread, work browser as a detached `python -m argus_collector.browser` process |

S0 blocks and states:

- bottom-left: `cv0.0.1.0 (3.10.2026 klo 14.32) <commit>` from `VERSION` + `build.json`; without an install `cv0.0.1.0 (ei asennustietoa)`; a mismatch is shown in red.
- Yhteys: `Ei yhteyttä` (no server connection exists before S1).
- Keruu: Käynnistä / Keskeytä / Pysäytä and both autostart settings present and disabled.
- Resurssit: lines from `diagnostics` (OS, Chrome, model, disk, memory, NVIDIA); errors in red, `Tarkistetaan…` while collecting.
- "Avaa työselain" (placed under Resurssit in S0 because the Huomio block needs a job in `needs_attention`): starts the launcher, which serves `test_site/` and opens the persistent-profile Chrome on it; the status line shows opening / opened / closed / failed with the launcher's error text.
- STOP file in the repo root or in the user data dir: red banner with the paths.

Tests (`tests/`) build props without a display and render the real window
under Xvfb when no display is present (skipped when neither exists).
