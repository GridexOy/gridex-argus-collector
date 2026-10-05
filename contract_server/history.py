"""change_kind / supersedes_observation_id of contact observations (TZ_SELAIN 8.8).

- `reconfirmed` with the value of a current (not superseded) observation of
  the same contact and field adds no row: that observation gets
  `last_confirmed_at` and a `reconfirmed` history entry, and the new
  observation_id becomes an alias of it. Without such a value it is stored new.
- `supersedes_observation_id` must name an observation (or alias) of the same
  canonical contact and the same field, else the event is rejected
  invalid_input; with `changed` the old observation gets `superseded_by` and a
  `changed` history entry.
"""

from __future__ import annotations

from contract_server.identity import observed_value, value_key
from contract_server.util import Json, latest


def resolve(contact: Json, observation_id: str) -> str | None:
    """The stored observation an id names: itself or the one it reconfirmed."""
    if observation_id in contact["observations"]:
        return observation_id
    alias = contact["aliases"].get(observation_id)
    return None if alias is None else str(alias["observation_id"])


def locate(state: Json, observation_id: str) -> tuple[Json, str] | None:
    """(contact, stored observation id) of any accepted observation id."""
    for contact in state["contacts"].values():
        stored = resolve(contact, observation_id)
        if stored is not None:
            return contact, stored
    return None


def _target_field(state: Json, contact_id: str | None, earlier: Json, target: str) -> str:
    """Field of the superseded observation; raises ValueError with the reason."""
    if target in earlier:
        return str(earlier[target])
    found = locate(state, target)
    if found is None:
        raise ValueError(f"supersedes_observation_id {target} is unknown")
    contact, stored = found
    if contact["canonical_contact_id"] != contact_id:
        raise ValueError(f"{target} belongs to another canonical contact")
    return str(contact["observations"][stored]["field"])


def supersede_error(state: Json, contact_id: str | None, observations: list[Json]) -> str | None:
    """Why the payload's supersedes ids are invalid, None when they are fine.

    `contact_id` is the payload's existing canonical contact (None: a new one);
    an earlier observation of the same payload counts as the same contact.
    """
    earlier: Json = {}
    for observation in observations:
        target = observation.get("supersedes_observation_id")
        name = observation["observation_id"]
        if target is not None:
            try:
                field = _target_field(state, contact_id, earlier, target)
            except ValueError as exc:
                return f"{name}: {exc}"
            if field != observation["field"]:
                return f"{name}: {target} is field {field!r}, not {observation['field']!r}"
        earlier[name] = observation["field"]
    return None


def same_value(contact: Json, observation: Json) -> str | None:
    """Latest current observation of the contact with this field and value."""
    field = observation["field"]
    wanted = value_key(field, observed_value(observation))
    for stored_id, stored in reversed(contact["observations"].items()):
        if stored["field"] != field or stored.get("superseded_by"):
            continue
        if value_key(field, observed_value(stored)) == wanted:
            return str(stored_id)
    return None


def mark_seen(contact: Json, when: str) -> None:
    """A new sighting: last_seen_at moves on and an older not_seen mark is cleared."""
    contact["last_seen_at"] = latest(contact["last_seen_at"], when)
    not_seen = contact.get("not_seen")
    if not_seen is not None and when >= not_seen["checked_at"]:
        contact["not_seen"] = None


def entry(kind: str, observation: Json, stored: Json) -> Json:
    return {
        "date": stored["observed_at"],
        "observation_id": observation["observation_id"],
        "kind": kind,
        "value": observation.get("normalized_value"),
        "run_id": stored["run_id"],
    }


def reconfirm(contact: Json, target: str, observation: Json, stored: Json) -> None:
    old = contact["observations"][target]
    old["last_confirmed_at"] = stored["observed_at"]
    old["history"].append(entry("reconfirmed", observation, stored))
    contact["aliases"][observation["observation_id"]] = {
        "observation_id": target,
        "run_id": stored["run_id"],
        "job_id": stored["job_id"],
        "event_id": stored["event_id"],
    }


def supersede(contact: Json, observation: Json, stored: Json) -> None:
    target = resolve(contact, observation["supersedes_observation_id"])
    if target is None or target == observation["observation_id"]:
        return
    old = contact["observations"][target]
    old["superseded_by"] = observation["observation_id"]
    old["history"].append(entry("changed", observation, stored))


def add(contact: Json, observation: Json, stored: Json) -> None:
    """Record one accepted observation on its contact by its change_kind."""
    if resolve(contact, observation["observation_id"]) is not None:
        return  # a repeated observation_id adds nothing
    kind = observation.get("change_kind") or "new"
    if kind == "reconfirmed":
        target = same_value(contact, observation)
        if target is not None:
            reconfirm(contact, target, observation, stored)
            return
    contact["observations"][observation["observation_id"]] = stored
    if kind == "changed" and observation.get("supersedes_observation_id"):
        supersede(contact, observation, stored)
