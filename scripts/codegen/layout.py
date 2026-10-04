"""Render every api_client file from the model and enforce the house limits on each.

The generator refuses to write output that the size gate (file <= 200 lines,
function <= 40 lines), ruff's E501 (100 columns) or the module README rule
(<= 40 lines) would reject, so a spec change that outgrows a renderer fails
here, loudly, instead of in a later gate.
"""

from __future__ import annotations

import ast

from codegen.chunking import MAX_FILE_LINES
from codegen.imports import MAX_LINE
from codegen.render_codec import render_codec
from codegen.render_contract import render_contract
from codegen.render_helpers import render_multipart, render_wire
from codegen.render_readme import render_readme
from codegen.render_repository import render_repository
from codegen.render_serialization import render_serialization
from codegen.render_service import render_service
from codegen.render_types import render_types
from codegen.spec import SpecError
from codegen.types import ClientModel

MAX_FUNCTION_LINES = 40
MAX_README_LINES = 40


def render_all(model: ClientModel, source: str) -> dict[str, str]:
    """{file name inside api_client/: content} for every generated file."""
    type_files, type_owner = render_types(model, source)
    codec_files, codec_owner = render_serialization(model, source, type_owner)
    outputs = {f"{module}.py": text for module, text in {**type_files, **codec_files}.items()}
    outputs["codec.py"] = render_codec(source, list(codec_files))
    outputs["wire.py"] = render_wire(source)
    outputs["multipart.py"] = render_multipart(source)
    outputs["repository.py"] = render_repository(model, source, type_owner, codec_owner)
    outputs["service.py"] = render_service(model, source, type_owner, codec_owner)
    outputs["contract.py"] = render_contract(model, source, type_owner, codec_owner)
    outputs["README.md"] = render_readme(model, source, len(type_files), len(codec_files))
    for name, text in outputs.items():
        check_limits(name, text)
    return outputs


def check_limits(name: str, text: str) -> None:
    lines = text.splitlines()
    limit = MAX_README_LINES if name.endswith(".md") else MAX_FILE_LINES
    if len(lines) > limit:
        raise SpecError(f"{name}: {len(lines)} lines > {limit}")
    if not name.endswith(".py"):
        return
    for number, line in enumerate(lines, start=1):
        if len(line) > MAX_LINE:
            raise SpecError(f"{name}:{number}: {len(line)} columns > {MAX_LINE}")
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > MAX_FUNCTION_LINES:
                raise SpecError(f"{name}: {node.name} is {length} lines > {MAX_FUNCTION_LINES}")
