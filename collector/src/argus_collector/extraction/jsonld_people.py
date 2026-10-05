"""People a page declares in JSON-LD (schema.org `Person`): read without the model.

Owner 05.10.2026: the card model (14b) is called only when the rules and
JSON-LD leave a page's people unread. A `Person` anywhere in a JSON-LD block
(top level, `@graph`, `employee`, `member`, `founder`, ...) with a `name`
becomes a card (`jobTitle`, `telephone`, `email` without `mailto:`); the
card is verified against the visible text like a model card.
"""

from __future__ import annotations

import json
from typing import Any

from argus_collector.extraction.service import PersonCard

MAX_PEOPLE = 200


def _is_person(node: dict[str, Any]) -> bool:
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return "Person" in kinds


def _text(node: dict[str, Any], key: str) -> str | None:
    value = node.get(key)
    if isinstance(value, list):
        value = next((v for v in value if isinstance(v, str)), None)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().removeprefix("mailto:").removeprefix("tel:")


def _walk(node: Any, out: list[PersonCard]) -> None:
    if len(out) >= MAX_PEOPLE:
        return
    if isinstance(node, list):
        for item in node:
            _walk(item, out)
        return
    if not isinstance(node, dict):
        return
    name = _text(node, "name")
    if _is_person(node) and name:
        out.append(PersonCard(name, _text(node, "jobTitle"), _text(node, "telephone"),
                              _text(node, "email")))
    for value in node.values():
        if isinstance(value, dict | list):
            _walk(value, out)


def people(blocks: list[str]) -> list[PersonCard]:
    """Person cards of the page's JSON-LD blocks, in document order."""
    out: list[PersonCard] = []
    for block in blocks:
        try:
            _walk(json.loads(block), out)
        except ValueError:
            continue
    return out
