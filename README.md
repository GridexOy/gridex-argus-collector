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

`VERSION` 0.4.3.0 (ARGUS20_TZ_TANDEM.md pairs A2 + A3): the panel claims
ARGUS jobs on "Käynnistä", walks each company from its seed within its
approved hosts and run budget (with the exhibition-country focus), and
streams evidence and `contact.observed` / `model.called` / `job.finished`
events through a SQLite outbox; leases, heartbeat commands, reconcile after
restart or outage, STOP. Until block 6 ships it runs against
`contract_server/` (the whole contract, every request schema-checked). See
`docs/ARGUS20_COLLECTOR_CHANGELOG.md` and `docs/ARGUS20_COLLECTOR_MODULES.md`.

## Layout

| Path | What |
|---|---|
| `collector/src/argus_collector/` | modules `runtime`, `storage`, `worker_auth`, `normalization`, `evidence`, `models`, `api_client` (generated), `discovery`, `extraction`, `browser`, `diagnostics`, `delivery`, `walk`, `scheduler`, `ui` (each: README, contract, service, repository, tests) |
| `collector/messages/fi.json` | every Finnish string of the panel and of `diagnose.ps1` |
| `collector/tests/` | cross-module tests (gates), `contract/` (contract tests of /api/collector through the generated client) and `fake_model_server.py` (test double of the model endpoint) |
| `contract_server/` | reference server of the whole OpenAPI contract, test-only: `python -m contract_server.server`, owner CLI `python -m contract_server.stand` |
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
