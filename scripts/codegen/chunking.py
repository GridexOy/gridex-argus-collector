"""Blocks of generated code, what they import, and packing them into <= 200-line files.

A Block is one top-level definition (a class, an alias, a codec pair) plus
the names it uses. `pack` fills `<prefix>_1.py`, `<prefix>_2.py`, ... in the
given order (dependencies first), so a later file only ever imports from
earlier ones and no import cycle can arise.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from codegen.imports import import_block
from codegen.spec import SpecError

MAX_FILE_LINES = 200
DEF_STARTS = ("def ", "class ", "@", "async def ")


@dataclass
class Needs:
    """Names a rendered block uses that its file must import."""

    stdlib: set[tuple[str, str]] = field(default_factory=set)  # (module, name)
    types: set[str] = field(default_factory=set)  # generated classes / aliases
    codecs: set[str] = field(default_factory=set)  # generated *_to_json / *_from_json
    fixed: set[tuple[str, str]] = field(default_factory=set)  # (api_client module, name)

    def merge(self, other: Needs) -> None:
        self.stdlib |= other.stdlib
        self.types |= other.types
        self.codecs |= other.codecs
        self.fixed |= other.fixed


@dataclass(frozen=True)
class Block:
    defines: tuple[str, ...]
    lines: tuple[str, ...]
    needs: Needs


Render = Callable[[str, list[Block], dict[str, str]], str]


def merged_needs(blocks: list[Block]) -> Needs:
    needs = Needs()
    for block in blocks:
        needs.merge(block.needs)
    return needs


def local_imports(
    needs: Needs, defined: set[str], type_owner: dict[str, str], codec_owner: dict[str, str]
) -> dict[str, set[str]]:
    """{api_client module: names} for everything `needs` lists that `defined` does not."""
    found: dict[str, set[str]] = {}
    for names, owner in ((needs.types, type_owner), (needs.codecs, codec_owner)):
        for name in names - defined:
            if name not in owner:
                raise SpecError(f"{name} is used before the file that defines it")
            found.setdefault(owner[name], set()).add(name)
    for module, name in needs.fixed:
        found.setdefault(module, set()).add(name)
    return found


def render_module(
    docstring: str,
    needs: Needs,
    local: dict[str, set[str]],
    body: list[str],
    plain: tuple[str, ...] = (),
) -> str:
    """Docstring, isort-ordered imports (`plain` ones as `import x`), the body.

    Like ruff's isort: two blank lines after the imports before a def/class,
    one before any other statement.
    """
    stdlib: dict[str, set[str]] = {}
    for module, name in needs.stdlib:
        stdlib.setdefault(module, set()).add(name)
    gap = [""] if body and body[0].startswith(DEF_STARTS) else []
    lines = [docstring, "", *import_block(stdlib, local, plain), *gap, *body]
    return "\n".join(lines).rstrip() + "\n"


def join_blocks(blocks: list[Block]) -> list[str]:
    lines: list[str] = []
    for block in blocks:
        if lines:
            lines += ["", ""]
        lines += block.lines
    return lines


def line_count(text: str) -> int:
    return len(text.splitlines())


def pack(prefix: str, blocks: list[Block], render: Render) -> tuple[dict[str, str], dict[str, str]]:
    """Greedy, order-preserving packing; returns ({module: text}, {defined name: module})."""
    files: dict[str, str] = {}
    owner: dict[str, str] = {}
    current: list[Block] = []
    for block in blocks:
        module = f"{prefix}_{len(files) + 1}"
        if current and line_count(render(module, [*current, block], owner)) > MAX_FILE_LINES:
            _close(module, current, render, files, owner)
            current = []
        current.append(block)
    if current:
        _close(f"{prefix}_{len(files) + 1}", current, render, files, owner)
    return files, owner


def _close(
    module: str, blocks: list[Block], render: Render, files: dict[str, str], owner: dict[str, str]
) -> None:
    text = render(module, blocks, owner)
    if line_count(text) > MAX_FILE_LINES:
        raise SpecError(f"{module}: {blocks[0].defines[0]} alone exceeds {MAX_FILE_LINES} lines")
    files[module] = text
    for block in blocks:
        for name in block.defines:
            owner[name] = module
