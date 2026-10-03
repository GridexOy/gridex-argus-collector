# extraction

Deterministic channels from a page and the verbatim check of the person
cards the model returns (TZ_SELAIN sections 8.2, 8.11; CLAUDE.md rule 8:
the model invents nothing). Does not depend on `models` (section 11).

Entry point: `contract.py`.

| Function | What it does |
|---|---|
| `extract_channels(html, text)` | phones and emails from `tel:`/`mailto:` hrefs (visible link text as quote), JSON-LD `telephone`/`email`/`faxNumber` (locator `jsonld:<block>/<pointer>`), Cloudflare `data-cfemail`, obfuscated addresses and phone runs in the canonical `text`; normalised, de-duplicated by value, each with a `TextSpan` when visible |
| `has_contact_signals(text, channels)` | whether a model card parse is worth a call |
| `card_from_json(obj)` | `PersonCard(name, title, phone, email)` from one model JSON object |
| `verify_card(card, text, channels)` | the verbatim check; returns `Contact` of `VerifiedField(value, quote, start, end, locator)` or None |

Verbatim rules of `verify_card`:
- `name` must be found in the canonical text (whitespace-insensitive) and
  look like a name, else the whole card is dropped;
- `title` is kept only when found in the text, else None;
- `phone` / `email`: the quote is found in the text and normalises to a
  value (locator `text`), or the normalised value equals a channel found in
  the html (quote and locator of that channel, e.g. `href:tel`); else None.

`repository.py` reads the html document (`html.parser`, no lxml) and
returns raw finds; `service.py` normalises through `normalization` and
locates quotes through `evidence.find_span`.
