# normalization

The one place where phones, emails, names and whitespace are normalised
(TZ_SELAIN section 11: dedup rules live here and nowhere else). Pure
functions, no I/O; the static tables (region codes, obfuscation spellings,
patterns) are in `repository.py`.

Entry point: `contract.py`.

| Function | Rule |
|---|---|
| `normalize_text(raw)` | NFC, whitespace runs -> one space, stripped |
| `normalize_name(raw)` | normalised text, or None when it has digits/@/brackets, no letters or > 80 chars |
| `normalize_email(raw)` | decodes `(at)`, `[at]`, ` at `, `(a)`, `(dot)`, `[dot]`, ` dot `, `(piste)`; drops `mailto:` and `?subject`; whole address lower-cased (raw quote keeps the case); None when not an address |
| `normalize_phone(raw, region="FI")` | E.164: `0xx` -> `+358xx`, `+`/`00` kept, `(0)` dropped, `ext`/`x` cut; None unless 7-15 digits and a confident prefix |
| `decode_cfemail(hex)` | Cloudflare `data-cfemail` -> address |
| `find_emails(text)` / `find_phones(text)` | raw substrings (obfuscated included) in order of appearance |
| `same_value(kind, a, b)` | equality after normalisation (`email`, `phone`, else text, case-insensitive) |

Callers always keep the raw quote next to the normalised value: the raw
form is the evidence, the normalised one is the value sent to ARGUS.
