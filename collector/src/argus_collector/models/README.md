# models

Adapter of the local model (M2, TZ_SELAIN section 4.2) on the RTX 4090:
any OpenAI-compatible chat endpoint on loopback. Default: Ollama
`http://127.0.0.1:11434/v1` with `qwen2.5:14b-instruct` (installed by
`scripts/install_model.ps1`); a llama.cpp server works unchanged.

Entry point: `contract.py`.

| Function | What it does |
|---|---|
| `health(endpoint, name)` | `GET <endpoint>/models`; `reachable` when it answers, `model_listed` when `name` (or `name:latest`) is served. Feeds the `Malli` line of diagnostics |
| `ModelClient(config, conn).chat_json(system, user, purpose)` | one chat completion with `response_format=json_object`, temperature 0, parsed to a dict; one retry on non-JSON, then `ModelError` |
| `ModelClient.chat(...)` | same, plain text |
| `ModelClient(config, conn, listener)` | 0.4.3.0: `listener(CallRecord)` hears every attempt (purpose, model, start, ms, tokens, ok): the job walk turns it into ARGUS `model.called` |
| `ModelConfig(endpoint, name, timeout_s=180, max_tokens=1024)` | from `model.endpoint` / `model.name` in `config.yaml` |

Rules:
- Proxy bypass: `repository.py` builds its opener with `ProxyHandler({})`; the
  Windows system proxy on MAIN-PC answers 127.0.0.1 with 502 and is never used.
- Every call, failed ones too, is a row in `model_calls` (provider `local`,
  model, purpose, prompt/completion tokens, ms, `cost_eur = 0`, ok, error)
  - TZ section 3.2 p.5, RULES E3. `repository.call_totals(conn)` sums them.
- The model searches nothing and generates no lists: callers (`walk`) show it
  one page and a numbered list of actions, and verify every returned value
  against the page text (`extraction.verify_card`).
- Cloud fallback does not exist here (TZ section 15 p.6).

Tests run against `collector/tests/fake_model_server.py`, a test double of
the endpoint; it never appears in the panel.
