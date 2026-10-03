# ARGUS 2.0 collector (Selain)

Local contact collector for ARGUS 2.0, running on a Windows workstation.
It claims a batch of companies from ARGUS, walks their own websites with
code and a local Chrome, and streams every contact it finds back to ARGUS
together with its evidence (snapshot, locator, quote, URL).

The only link to ARGUS is the contract `docs/ARGUS20_COLLECTOR_OPENAPI.json`.
Until ARGUS block 6 ships, the collector is tested against the reference
server in `contract_server/` (test-only, never deployed).

Specification and working rules are in `docs/` (in Russian, the owner's
language); code and this README stay in English. Start with `START_HERE.md`.

## Status

`VERSION` 0.4.1.0 (owner decision 03.10.2026: local model + browser walk
first): diagnostics, fixture site, panel with the Keruu block that walks a
company site in the visible Chrome with the local model (Ollama,
`qwen2.5:14b-instruct`) and lists verified contacts with evidence. See
`docs/ARGUS20_COLLECTOR_CHANGELOG.md` and `docs/ARGUS20_COLLECTOR_MODULES.md`.

## Layout

| Path | What |
|---|---|
| `collector/src/argus_collector/` | modules `runtime`, `storage`, `normalization`, `evidence`, `models`, `discovery`, `extraction`, `browser`, `diagnostics`, `walk`, `ui` (each: README, contract, service, repository, tests) |
| `collector/messages/fi.json` | every Finnish string of the panel and of `diagnose.ps1` |
| `collector/tests/` | cross-module tests (gates) and `fake_model_server.py` (test double of the model endpoint) |
| `test_site/` | fixture site served by `python -m test_site.server`; gold files in `test_site/gold/` |
| `scripts/` | `diagnose.ps1`, `install.ps1`, `install_model.ps1` (Ollama + model on the GPU), `start.ps1`, `run_gates.py` / `run_gates.ps1`, `check_*.ps1`, `gates/` |
| `config.example.yaml` | settings without secrets; copied to `%LOCALAPPDATA%\Gridex\ArgusCollector\config.yaml` on install |

## Windows (MAIN-PC), PowerShell 5.1

```
& {
  Set-Location 'C:\dev\gridex-argus-collector' -ErrorAction Stop
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_model.ps1; if ($LASTEXITCODE -ne 0) { Write-Host 'STOP: model install failed (see the lines above)'; return }
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install.ps1; if ($LASTEXITCODE -ne 0) { Write-Host 'STOP: install failed'; return }
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
}
```

`install.ps1` refuses a dirty tree, any branch but `main` and any red gate.
`scripts\diagnose.ps1` prints the machine check; `-Json` prints what the panel reads.

## Development (any OS)

```
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/pip install -e . --no-deps
.venv/bin/python scripts/run_gates.py
.venv/bin/python -m pytest
.venv/bin/python -m argus_collector.ui        # the panel (needs a display)
```

Outside Windows the work browser is Playwright's bundled Chromium
(`PLAYWRIGHT_BROWSERS_PATH` or `playwright install chromium`); on Windows it
is the installed Google Chrome and no `playwright install` is needed.
