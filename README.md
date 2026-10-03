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

Bootstrap only: documentation and rules, no code yet. Stage S0 (diagnostics,
test site, panel with version) is the first step, see
`docs/ARGUS20_TZ_SELAIN.md` §2.3 and §13.1.
