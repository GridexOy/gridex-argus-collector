# diagnostics

Machine facts and their states for the Resurssit block and for
`scripts/diagnose.ps1` (TZ_SELAIN section 12.1): Windows, Chrome, NVIDIA
driver/GPU, RAM, disk, local model endpoint.

Entry point: `contract.py`.

| Function | What it does |
|---|---|
| `collect(model_endpoint, model_name, use_powershell)` | on Windows runs `scripts/diagnose.ps1 -Json -ModelEndpoint ... -ModelName ...` and parses it; elsewhere probes with Python (`repository.py`); empty model strings = `models` defaults |
| `parse_report_json(text)` | parses the `argus-collector-diagnose/1` document and re-derives the states; a drift between the script's states and the Python rules raises `ValueError` |
| `report_to_json(report)` | the same document from a Python-collected report |

States (`service.py`, same rules as the script):

| Field | Values | Rule |
|---|---|---|
| chrome | `available` / `missing` | executable path found |
| gpu | `nvidia` / `other` / `missing` | adapter name contains "NVIDIA" / any other name / none |
| disk | `ok` / `low` | `low` when used > 85 % (WAYS section 9) |
| model | `gpu` / `cpu` / `none` | `none` when `GET <endpoint>/models` does not answer or does not list the configured model (`models.health`, no system proxy); `gpu` when it does, the GPU is NVIDIA and >= 1024 MB of GPU memory is in use (Ollama loads the model on first call, so `cpu` can show until the first walk); otherwise `cpu` |

The word "unknown" never appears: every field has a value or an explicit
`missing`/`none` state. The script and the panel show the same Finnish lines
because both read `collector/messages/fi.json`.
