# extraction

Deterministic channels from a page and the verbatim check of the person
cards the model returns (TZ_SELAIN sections 8.2, 8.11; CLAUDE.md rule 8:
the model invents nothing). Does not depend on `models` (section 11).

Entry point: `contract.py`.

| Function | What it does |
|---|---|
| `extract_channels(html, text, region)` | phones and emails from `tel:`/`mailto:` hrefs (visible link text as quote), JSON-LD `telephone`/`email`/`faxNumber` (locator `jsonld:<block>/<pointer>`), Cloudflare `data-cfemail`, obfuscated addresses and phone runs in the canonical `text`; normalised, de-duplicated by value, each with a `TextSpan` when visible |
| `has_contact_signals(text, channels)` | whether a model card parse is worth a call |
| `card_from_json(obj)` | `PersonCard(name, title, phone, email)` from one model JSON object |
| `verify_card(card, text, channels, region)` | the verbatim check; returns `Contact` of `VerifiedField(value, quote, start, end, locator)` or None |
| `classify_unattached(channel, text)` | 0.4.3.0 (`roles.py`): a channel no person claims is `organization_channel` (generic mailbox, switchboard line, JSON-LD), `office` (its line names an office) or `unassigned_channel`, with the binding to send |
| `country_sections(text)` / `region_resolver` / `office_lines` | 0.4.4.0 (`sections.py`, owner 05.10.2026): on a page naming >= 3 countries on lines of their own, each country heading starts a section; a phone in it is read in that country (`09-7422 3300` under Finland -> +358974223300); the office's company line and address lines. A number labelled fax (`Fax`, `Faksi`, `Telefax`) or JSON-LD `faxNumber` is a channel of kind `fax` (0.4.7.0: sent only as extra `fax`) |
| `jsonld_people(html)` / `panel_sections(text, panels)` | 0.4.8.0 (`jsonld_people.py`, `sections.py`): schema.org `Person` items as cards (read without the model, verified like model cards); a selected tab labelled with a country makes its panel that country's section |
| `html_language(html)` | `<html lang>`; with the URL it gives the phone region (`normalization.region_for_page`) |
| `text_cards(text, channels)` | 0.4.8.6 (`text_cards.py`): cards by rule: a name line, up to 2 plain lines (the first is the title), the person's own phone / email below; a generic mailbox or switchboard line is the company's and ends the card |
| `email_patterns(text)` / `pattern_address(p, name)` | 0.4.8.6 (`email_pattern.py`, owner 06.10.2026): an address pattern the page states (`firstname.lastname@reimax.net`, `etunimi.sukunimi@`, `vorname.nachname@`) with its line as quote, and the address it gives a full name; a placeholder is never a channel or a person's email (RULES K3) |

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
