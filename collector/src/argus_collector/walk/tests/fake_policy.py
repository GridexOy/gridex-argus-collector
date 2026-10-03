"""Scripted replies of the fake model for walk tests (test double, tests only).

The policy reads the prompts the walk sends and answers like a careful
model would: people it can see in the page text (from the gold file, plus
one invented person that the verbatim check must drop) and the most
promising element to act on (reveal button, next page, team, contact).
"""

from __future__ import annotations

import json
import re
from typing import Any

ELEMENT_RE = re.compile(r"^\[(\d+)\] (link|button): '(.*?)'(?: -> (\S+))?$", re.MULTILINE)
GHOST = {"name": "Ghost Person", "title": "Chief Ghost", "phone": "050 000 0000", "email": None}
PRIORITY = ("yhteystiedot", "seuraava", "team", "contact")


def page_text(user: str) -> str:
    start = user.find("PAGE TEXT:")
    end = user.find("\n\nELEMENTS:") if "ELEMENTS:" in user else user.rfind("\n\nJSON:")
    return user[start + len("PAGE TEXT:") : end] if start >= 0 else ""


def elements(user: str) -> list[tuple[int, str, str, str]]:
    return [(int(i), k, t, h or "") for i, k, t, h in ELEMENT_RE.findall(user)]


class GoldPolicy:
    """`policy(system, user) -> content` for FakeModelServer."""

    def __init__(self, persons: list[dict[str, Any]]) -> None:
        self.persons = persons
        self.card_calls = 0
        self.action_calls = 0

    def __call__(self, system: str, user: str) -> str:
        if "numbered list" in system:
            self.action_calls += 1
            return json.dumps(self.action(user))
        self.card_calls += 1
        return json.dumps({"people": self.cards(page_text(user))})

    def cards(self, text: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = [dict(GHOST)]
        for person in self.persons:
            if person["name"] not in text:
                continue
            email = person["email"] if person["email"] in text else person.get("email_text")
            found.append(
                {
                    "name": person["name"],
                    "title": person["title"],
                    "phone": person["phone"],
                    "email": email or person["email"],
                }
            )
        return found

    def action(self, user: str) -> dict[str, Any]:
        found = elements(user)
        for word in PRIORITY:
            for index, kind, text, _ in found:
                if word in text.lower():
                    return {"action": "navigate" if kind == "link" else "click", "index": index}
        return {"action": "finish", "index": None, "reason": "nothing promising left"}
