"""Known contacts of a re-run: change_kind of observations and contact.freshness.

TZ_SELAIN 8.8, ARGUS20_TZ_TANDEM.md A4. A known person is the same contact
when the normalised full name matches; a known office / company channel when
one of its phone or email values matches. An observed value equal to a known
one is `reconfirmed`, a different value of a known field is `changed` (it
supersedes the known observation), anything else is `new`. At the end of a
run every field of every known contact gets a freshness check: reconfirmed /
changed / not_seen_in_checked_scope (the frontier was exhausted) /
not_checked. `KnownContact.fields` (docs/ANSWERS_S5.md section 1): key = the
field name, an extra field by its `extra_label` (`country`, `department`,
`office_name`, `address`); value = the normalized value, a string or a list
of strings (first = primary). An object with `value` (and `observation_id`)
or a list of such objects is read too.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from argus_collector.api_client import contract as api

NAME = "full_name"
CHANNELS = ("phone", "email")
NEW, RECONFIRMED, CHANGED = "new", "reconfirmed", "changed"
NOT_SEEN, NOT_CHECKED = "not_seen_in_checked_scope", "not_checked"
SPACES = re.compile(r"\s+")


def norm(field: str, value: str) -> str:
    if field == "phone":
        return "+" + re.sub(r"\D", "", value)
    return SPACES.sub(" ", value).strip().casefold()


@dataclass(frozen=True)
class KnownValue:
    value: str
    observation_id: str | None


@dataclass(frozen=True)
class Known:
    contact_id: str
    entity_type: str
    fields: dict[str, tuple[KnownValue, ...]]

    def keys(self, field: str) -> set[str]:
        return {norm(field, v.value) for v in self.fields.get(field, ())}


def _values(raw: Any) -> tuple[KnownValue, ...]:
    out: list[KnownValue] = []
    for item in raw if isinstance(raw, list) else [raw]:
        if isinstance(item, dict):
            value = item.get("value") or item.get("normalized_value") or item.get("raw_value")
            obs = item.get("observation_id")
        else:
            value, obs = item, None
        if isinstance(value, str | int | float) and str(value).strip():
            out.append(KnownValue(str(value), str(obs) if obs else None))
    return tuple(out)


def parse_known(items: Iterable[api.KnownContact]) -> list[Known]:
    out = []
    for item in items:
        fields = {str(f): _values(raw) for f, raw in dict(item.fields).items()}
        out.append(Known(item.canonical_contact_id, item.entity_type.value,
                         {f: v for f, v in fields.items() if v}))
    return out


class KnownIndex:
    def __init__(self, known: list[Known]) -> None:
        self.known = known
        self.by_name = {norm(NAME, v.value): k for k in known if k.entity_type == "person"
                        for v in k.fields.get(NAME, ())}
        self.by_channel = {norm(f, v.value): k for k in known if k.entity_type != "person"
                           for f in CHANNELS for v in k.fields.get(f, ())}

    def match(self, entity_type: str, key: str, values: dict[str, set[str]]) -> Known | None:
        """The known contact an entity of this job is (person by name, else by a channel)."""
        if entity_type == "person":
            return self.by_name.get(norm(NAME, key.split("|", 1)[0]))
        for field in CHANNELS:
            for value in values.get(field, set()):
                found = self.by_channel.get(norm(field, value))
                if found is not None:
                    return found
        return None

    def change(self, known: Known | None, field: str, value: str) -> tuple[str, str | None]:
        """(change_kind, supersedes_observation_id) of one observed value."""
        if known is None or field not in known.fields:
            return NEW, None
        if norm(field, value) in known.keys(field):
            return RECONFIRMED, None
        return CHANGED, known.fields[field][0].observation_id


@dataclass(frozen=True)
class RunSight:
    """What a run saw of one entity: values per field and their observation ids."""

    entity_type: str
    values: dict[str, set[str]]
    obs_ids: dict[tuple[str, str], str]  # (field, value) -> observation id


def sights(entity_types: dict[str, str], known_obs: dict[str, str]) -> dict[str, RunSight]:
    """entity_key -> RunSight from the checkpoint's `known_obs` (`key|field|value` -> id).

    An observation belongs to the longest entity key it starts with (a person
    key `name|email` is longer than `name`)."""
    out = {key: RunSight(kind, {}, {}) for key, kind in entity_types.items()}
    longest_first = sorted(entity_types, key=len, reverse=True)
    for obs_key, obs_id in known_obs.items():
        owner = next((k for k in longest_first if obs_key.startswith(k + "|")
                      and "|" in obs_key[len(k) + 1:]), None)
        if owner is None:
            continue
        field, value = obs_key[len(owner) + 1:].split("|", 1)
        out[owner].values.setdefault(field, set()).add(value)
        out[owner].obs_ids[(field, value)] = obs_id
    return out


@dataclass(frozen=True)
class Scope:
    description: str
    exhausted: bool  # coverage.frontier_status == exhausted
    checked_at: str


def _check(known: Known, field: str, sight: RunSight | None, scope: Scope,
           evidence_of: dict[str, str]) -> api.FreshnessCheck:
    status, obs_id = (NOT_SEEN if scope.exhausted else NOT_CHECKED), None
    seen = sight.values.get(field, set()) if sight else set()
    if sight is not None and seen:
        same = [v for v in seen if norm(field, v) in known.keys(field)]
        value = same[0] if same else sorted(seen)[0]
        status = RECONFIRMED if same else CHANGED
        obs_id = sight.obs_ids.get((field, value))
    evidence = [evidence_of[obs_id]] if obs_id and obs_id in evidence_of else []
    return api.FreshnessCheck(
        canonical_contact_id=known.contact_id, field=field,
        status=api.FreshnessCheckStatus(status), scope_description=scope.description,
        evidence_ids=evidence, checked_at=scope.checked_at, observation_id=obs_id,
    )


def freshness_checks(index: KnownIndex, seen: dict[str, RunSight], scope: Scope,
                     evidence_of: dict[str, str]) -> list[api.FreshnessCheck]:
    """One check per field of every known contact (TZ_SELAIN 8.8)."""
    matched: dict[str, RunSight] = {}
    for key, sight in seen.items():
        known = index.match(sight.entity_type, key, sight.values)
        if known is not None:
            matched.setdefault(known.contact_id, sight)
    return [
        _check(known, field, matched.get(known.contact_id), scope, evidence_of)
        for known in index.known for field in sorted(known.fields)
    ]
