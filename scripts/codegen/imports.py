"""Render import blocks exactly the way ruff's isort rule (I001) wants them.

Sections: `__future__`, stdlib, then this package. Inside a section plain
`import x` lines come first, then `from x import ...` lines; modules sort
naturally (`types_2` before `types_10`), members by type (CONSTANTS, then
Classes, then functions) and naturally within a type. A from-import that fits
in MAX_LINE columns stays on one line, otherwise it is wrapped one name per
line with a trailing comma.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

MAX_LINE = 100
PACKAGE = "argus_collector.api_client"
_DIGITS = re.compile(r"(\d+)")


def natural_key(text: str) -> list[int | str]:
    return [int(part) if part.isdigit() else part for part in _DIGITS.split(text)]


def member_key(name: str) -> tuple[int, list[int | str], list[int | str]]:
    if len(name) > 1 and name.isupper():
        group = 0
    elif name[:1].isupper():
        group = 1
    else:
        group = 2
    return group, natural_key(name.lower()), natural_key(name)


def module_key(module: str) -> tuple[list[int | str], list[int | str]]:
    return natural_key(module.lower()), natural_key(module)


def from_import(module: str, names: Iterable[str]) -> list[str]:
    ordered = sorted(set(names), key=member_key)
    one_line = f"from {module} import {', '.join(ordered)}"
    if len(one_line) <= MAX_LINE:
        return [one_line]
    return [f"from {module} import (", *(f"    {name}," for name in ordered), ")"]


def import_block(
    stdlib: dict[str, set[str]],
    local: dict[str, set[str]],
    plain: Iterable[str] = (),
) -> list[str]:
    """`from __future__` + stdlib (`plain` modules as `import x`) + this package's modules.

    `local` is keyed by module name inside api_client; the key "" imports
    from the package itself (`from argus_collector.api_client import x`).
    """
    lines = ["from __future__ import annotations", ""]
    std = [f"import {module}" for module in sorted(set(plain), key=module_key)]
    for module in sorted(stdlib, key=module_key):
        std += from_import(module, stdlib[module])
    if std:
        lines += [*std, ""]
    full = {f"{PACKAGE}.{module}".rstrip("."): names for module, names in local.items()}
    for module in sorted(full, key=module_key):
        lines += from_import(module, full[module])
    if local:
        lines.append("")
    return lines
