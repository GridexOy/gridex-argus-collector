# evidence

Snapshots, hashes and locators (TZ_SELAIN section 8.12, RULES E1-E3). A
contact field is recorded only together with an `evidence_id`, a locator
and a quote; this module makes those three things.

Entry point: `contract.py`.

| Function | What it does |
|---|---|
| `canonical_text(text)` | NFC, CRLF -> LF, inline whitespace collapsed, blank lines dropped; the text the model reads and spans point into |
| `sha256_text(text)` | hex sha256 of the utf-8 bytes |
| `find_span(text, quote)` | `TextSpan(start, end, quote, text_sha256)` in code points; exact match first, then whitespace-insensitive; None when absent |
| `store_snapshot(conn, url, final_url, html, text, base_dir)` | writes `<base>/<sha[:2]>/<sha>.html` + `.txt` atomically (tmp + rename), inserts the `evidence_manifest` row; `evidence_id` = sha256 of the html, so the same page stored twice is one snapshot |
| `evidence_dir()` | `<user_data_dir>/evidence` |

`service.py` is pure (hashes, spans, paths), `repository.py` touches the
disk and the `evidence_manifest` table of the collector database
(`storage` owns the schema).
