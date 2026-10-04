# worker_auth

Local storage of the ARGUS connection (ARGUS20_TZ_TANDEM.md pair A1): the
worker token the owner enters in the "Yhteys" block, and the address +
worker_id typed alongside it. Nothing here talks to the network -- see
`api_client` for the actual heartbeat call.

Entry point: `contract.py`.

| Function | Does |
|---|---|
| `load_connection()` / `save_connection(base_url, worker_id)` | plain JSON, `connection.json` in the user data dir -- not secret |
| `load_token()` / `save_token(token)` / `clear_token()` | the bearer token, `worker_token.bin`, DPAPI-encrypted on Windows |
| `mask_token(token)` | last 4 characters only, for logs and the screen (TZ_TANDEM A1.2) |

DPAPI (`CryptProtectData`/`CryptUnprotectData` via `ctypes.windll.crypt32`)
ties the ciphertext to the current Windows user account; there is no key to
manage or lose (CLAUDE.md rule 7, no secrets handled by hand). Off Windows
(Linux/macOS tests, CI) there is no DPAPI, so `repository.py` falls back to a
reversible XOR -- clearly not secure, it only keeps this module's logic
testable outside Windows; nothing off-Windows claims to protect a real
secret. `load_token()` returns `None` (not an exception) when the file is
missing or fails to decrypt, so the caller just shows "not connected".
