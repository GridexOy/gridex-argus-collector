# worker_auth

Local storage of the ARGUS connection (ARGUS20_TZ_TANDEM.md pair A1): the
pairing key the owner pastes into the "Yhteys" block
(`argus://pair?url=&worker=&token=`, 0.4.7.0) is parsed here and kept as the
address + worker_id (plain) and the token (DPAPI). Nothing here talks to the
network -- see `api_client` for the actual heartbeat call.

Entry point: `contract.py`.

| Function | Does |
|---|---|
| `load_connection()` / `save_connection(base_url, worker_id)` | plain JSON, `connection.json` in the user data dir -- not secret |
| `load_token()` / `save_token(token)` / `clear_token()` | the bearer token, `worker_token.bin`, DPAPI-encrypted on Windows |
| `mask_token(token)` | last 4 characters only, for logs and the screen (TZ_TANDEM A1.2) |
| `parse_pairing_key(text)` / `save_pairing(key)` | the pasted key -> `PairingKey(base_url, worker_id, token)` or `PairingKeyError(reason, field)`: format, missing, duplicate, characters, url, https (http only for this PC); `+` stays `+`, a trailing `/api/collector` is dropped |
| `is_loopback(address)` | 127.0.0.1 / localhost / ::1: never through the system proxy |

DPAPI (`CryptProtectData`/`CryptUnprotectData` via `ctypes.windll.crypt32`)
ties the ciphertext to the current Windows user account; there is no key to
manage or lose (CLAUDE.md rule 7, no secrets handled by hand). Off Windows
(Linux/macOS tests, CI) there is no DPAPI, so `repository.py` falls back to a
reversible XOR -- clearly not secure, it only keeps this module's logic
testable outside Windows; nothing off-Windows claims to protect a real
secret. `load_token()` returns `None` (not an exception) when the file is
missing or fails to decrypt, so the caller just shows "not connected".
