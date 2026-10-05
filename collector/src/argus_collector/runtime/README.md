# runtime

Facts about the installation that every other module needs and nobody else
owns: where the user data directory is, which VERSION the source tree has,
what `install.ps1` wrote into `build.json`, and whether a `STOP` file exists.

Entry point: `contract.py`.

| Function | Returns |
|---|---|
| `repo_root()` | directory that holds `VERSION` (source tree or installed copy) |
| `user_data_dir()` | `%LOCALAPPDATA%\Gridex\ArgusCollector` on Windows, `$XDG_DATA_HOME/Gridex/ArgusCollector` elsewhere, `ARGUS_COLLECTOR_HOME` overrides |
| `browser_profile_dir()` | `<user_data_dir>/browser-profile` (TZ_SELAIN section 7) |
| `current_version_status()` | VERSION file + `build.json`; a mismatch or a bad format is reported in `error` |
| `version_line(status, text)` | `cv0.0.1.0 (3.10.2026 klo 14.32) a1b2c3d`, or `cv0.0.1.0 (<text>)` when not installed |
| `stop_files()` / `stop_reason()` | kill switch: `STOP` in repo root or in the user data dir |
| `journal(channel, message)` / `prune_journal()` / `safe_url(url)` | 0.4.3.0 (`journal.py`): `<user_data_dir>/logs/collector-YYYY-MM-DD.log`, lines `<UTC> <channel>: <message>` with the Lokit channels `http` / `browser` / `extraction` / `delivery` / `model`; no contact values, no tokens, URLs without query; 14 days |
| `load_config()` | `Config(model_endpoint, model_name, model_navigation, model_vision, walk_page_budget, test_site_port, network_proxy)` (0.4.8.0: `model.navigation` default `qwen2.5:7b`, `model.vision` default `qwen2.5-vl:7b`, "" switches one off) from the first `config.yaml` found; empty model strings mean the `models` defaults |

`repository.py` reads the disk on every call (no caching), `service.py` is
pure and fully unit-tested. `build.json` is written only by
`scripts/install.ps1`: `{"version", "commit", "built_at"}`.
