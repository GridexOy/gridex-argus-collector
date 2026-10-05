"""Structural binding of verified person fields (TZ_SELAIN section 8.11, 9.4).

The model only groups text; whether a phone really belongs to a name is
decided here from the DOM: of all innermost elements holding the name and
all innermost elements holding the value, the pair that meets in the
smallest common ancestor wins (a heading with the same words is not the
card). When that ancestor is a table row -> `table_row`; when it is a small container that
holds no other person's name or value -> `card`; otherwise (only the page
body joins them, or another person is inside) -> `proximity_only`; a part
that cannot be found in the DOM -> `none`. Text is compared lower-case with
all whitespace removed, so `<b>Anna</b> Virtanen` still matches. Each person
also gets its group: the nearest h2-h6 / legend / summary before its card in
the same tab panel or section (`Myynti`), else the label of its tab.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

BINDING_CARD = "card"
BINDING_ROW = "table_row"
BINDING_PROXIMITY = "proximity_only"
BINDING_NONE = "none"
MAX_CARD_TEXT = 1500

BINDING_JS = """
(probe) => {
  const squash = s => (s || '').toLowerCase().replace(/\\s+/g, '');
  const digits = s => (s || '').replace(/\\D+/g, '');
  const skip = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE']);
  const all = document.body ? Array.from(document.body.querySelectorAll('*')) : [];
  const texts = new Map();
  const textOf = el => {
    if (!texts.has(el)) texts.set(el, squash(el.textContent));
    return texts.get(el);
  };
  const minimal = needle => {
    if (!needle) return [];
    const hits = all.filter(el => !skip.has(el.tagName) && textOf(el).includes(needle));
    const set = new Set(hits);
    return hits.filter(el => !Array.from(el.children).some(c => set.has(c)));
  };
  const byHref = v => {
    if (v.kind === 'email') {
      for (const a of document.querySelectorAll('a[href^="mailto:" i]'))
        if (a.getAttribute('href').toLowerCase().includes(v.value.toLowerCase())) return a;
    } else if (v.kind === 'phone') {
      const want = digits(v.value).slice(-8);
      for (const a of document.querySelectorAll('a[href^="tel:" i]'))
        if (want && digits(a.getAttribute('href')).endsWith(want)) return a;
    }
    return null;
  };
  const meet = (a, b) => {
    const up = new Set();
    for (let x = a; x; x = x.parentElement) up.add(x);
    for (let y = b; y; y = y.parentElement) if (up.has(y)) return y;
    return null;
  };
  const closest = (names, values) => {
    let best = null, size = Infinity;
    for (const n of names) for (const v of values) {
      const top = meet(n, v);
      if (top && textOf(top).length < size) { best = top; size = textOf(top).length; }
    }
    return best;
  };
  const own = p => [squash(p.name), ...p.values.map(v => squash(v.text))].filter(s => s);
  const owners = probe.persons.map(own);
  const personNames = new Set(probe.persons.map(p => squash(p.name)));
  const groupOf = card => {
    if (!card) return {group: '', panel: false};
    const box = card.closest('[role="tabpanel"], section, article, fieldset, details')
      || document.body;
    const panel = !!card.closest('[role="tabpanel"]');
    let best = null;
    for (const h of box.querySelectorAll('h2, h3, h4, h5, h6, [role="heading"], legend, summary')) {
      if (h.contains(card) || card.contains(h)) continue;
      if (!(h.compareDocumentPosition(card) & Node.DOCUMENT_POSITION_FOLLOWING)) continue;
      const t = (h.innerText || '').replace(/\\s+/g, ' ').trim();
      if (t && t.length <= 60 && !personNames.has(squash(t))) best = t;
    }
    if (best) return {group: best, panel};
    const tabpanel = card.closest('[role="tabpanel"]');
    const tab = tabpanel && tabpanel.getAttribute('aria-labelledby')
      ? document.getElementById(tabpanel.getAttribute('aria-labelledby')) : null;
    const label = tab ? (tab.innerText || '').replace(/\\s+/g, ' ').trim() : '';
    return {group: label, panel: !!tab};
  };
  return probe.persons.map((p, i) => {
    const names = minimal(squash(p.name));
    const others = owners.filter((_, j) => j !== i).flat();
    const cards = [];
    const values = p.values.map(v => {
      let found = minimal(squash(v.text));
      if (!found.length) { const a = byHref(v); found = a ? [a] : []; }
      if (!names.length || !found.length) return 'none';
      const top = closest(names, found);
      const root = document.documentElement;
      if (!top || top === document.body || top === root) return 'proximity_only';
      const t = textOf(top);
      if (t.length > __MAX__) return 'proximity_only';
      const mine = new Set(own(p));
      if (others.some(o => !mine.has(o) && t.includes(o))) return 'proximity_only';
      cards.push(top);
      return top.closest('tr') ? 'table_row' : 'card';
    });
    return {values, ...groupOf(cards[0] || names[0] || null)};
  });
}
""".replace("__MAX__", str(MAX_CARD_TEXT))


@dataclass(frozen=True)
class ProbeValue:
    text: str  # the quote as seen in the page text
    kind: str  # email | phone | text
    value: str  # normalised value (for matching tel:/mailto: hrefs)


@dataclass(frozen=True)
class PersonProbe:
    name: str
    values: tuple[ProbeValue, ...]


def probe_payload(persons: list[PersonProbe]) -> dict[str, Any]:
    return {
        "persons": [
            {
                "name": p.name,
                "values": [{"text": v.text, "kind": v.kind, "value": v.value} for v in p.values],
            }
            for p in persons
        ]
    }


@dataclass(frozen=True)
class PersonBinding:
    values: tuple[str, ...]  # one binding per probed value
    group: str = ""  # group heading or tab label of the person's card ("" none)
    in_panel: bool = False  # the group is inside a tab panel (a department for sure)


def parse_result(raw: object, persons: list[PersonProbe]) -> list[PersonBinding]:
    """JS result -> one binding per probed value and the group; malformed -> `none`."""
    allowed = {BINDING_CARD, BINDING_ROW, BINDING_PROXIMITY, BINDING_NONE}
    rows = raw if isinstance(raw, list) else []
    out: list[PersonBinding] = []
    for index, person in enumerate(persons):
        item = rows[index] if index < len(rows) and isinstance(rows[index], dict) else {}
        row = item.get("values") if isinstance(item.get("values"), list) else []
        assert isinstance(row, list)
        values = [str(row[i]) if i < len(row) else BINDING_NONE for i in range(len(person.values))]
        group = str(item.get("group", "") or "")[:120]
        bound = tuple(v if v in allowed else BINDING_NONE for v in values)
        out.append(PersonBinding(bound, group, item.get("panel") is True))
    return out
