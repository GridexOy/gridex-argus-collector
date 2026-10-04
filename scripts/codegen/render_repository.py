"""Render api_client/repository.py: the stdlib `urllib.request` HTTP transport.

The transport skeleton (openers, ApiError, the POST helper, error parsing)
is fixed boilerplate the generator always emits the same way; only the
imports and the one function per manifest operation vary with the manifest.
"""

from __future__ import annotations

from codegen.naming import pascal_to_snake
from codegen.types import ClientModel, OperationSpec

DOC = (
    '"""Generated HTTP transport for the api_client module (mechanically generated).\n\n'
    "Source: {source}.\n"
    "Do not edit by hand -- see api_client/README.md to regenerate.\n"
    'stdlib-only `urllib.request`, no third-party dependency. `proxy_mode="system"`\n'
    "honors the OS proxy configuration (needed for the real ARGUS host,\n"
    "ARGUS20_TZ_TANDEM.md pair A1 item 4); `proxy_mode=\"direct\"` never uses a\n"
    "proxy (needed against loopback/contract_server, where the Windows system\n"
    "proxy answers 127.0.0.1 with a 502 -- see ARGUS20_COLLECTOR_CHANGELOG.md,\n"
    "commit 6b6467b). The caller decides the mode; this module never inspects\n"
    "the target host to guess it -- that is config-reading, a different module's job.\n"
    '"""'
)
BOILERPLATE = '''

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Literal

{func_imports}
from argus_collector.api_client.service import (
{service_imports})

SYSTEM_OPENER = urllib.request.build_opener()
DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({{}}))
ProxyMode = Literal["system", "direct"]


class ApiError(RuntimeError):
    """A non-2xx response, or a 2xx one whose body did not parse. `error` is the
    parsed Error body when the server sent one."""

    def __init__(self, status: int, error: Error | None, retry_after: str | None, raw: str) -> None:
        detail = error.detail if error is not None else raw[:300]
        super().__init__(f"HTTP {{status}}: {{detail}}")
        self.status = status
        self.error = error
        self.retry_after = retry_after


def _opener(proxy_mode: ProxyMode) -> urllib.request.OpenerDirector:
    return DIRECT_OPENER if proxy_mode == "direct" else SYSTEM_OPENER


def _post(
    base_url: str,
    path: str,
    token: str,
    body: dict[str, Any],
    proxy_mode: ProxyMode,
    timeout_s: float,
) -> tuple[int, bytes]:
    url = base_url.rstrip("/") + path
    headers = {{
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {{token}}",
    }}
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with _opener(proxy_mode).open(request, timeout=timeout_s) as response:
            return int(response.status), bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise _api_error_from_http(exc) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ApiError(0, None, None, f"{{url}}: {{exc}}") from exc


def _api_error_from_http(exc: urllib.error.HTTPError) -> ApiError:
    raw = exc.read().decode("utf-8", errors="replace")
    retry_after = exc.headers.get("Retry-After") if exc.headers is not None else None
    parsed: Error | None = None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            parsed = error_from_json(data)
    except (ValueError, KeyError, TypeError):
        parsed = None
    return ApiError(exc.code, parsed, retry_after, raw[:300])


def _parse_json_body(status: int, raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise ApiError(status, None, None, f"not JSON: {{raw[:120]!r}}") from exc
    if not isinstance(data, dict):
        raise ApiError(status, None, None, f"not a JSON object: {{raw[:120]!r}}")
    return data
'''


def render_repository(model: ClientModel, source_rel: str) -> str:
    service_imports = sorted({"Error"} | _operation_type_names(model.operations))
    to_json_types = {op.request_schema for op in model.operations}
    from_json_types = {"Error"} | {op.response_schema for op in model.operations}
    func_imports = _render_func_imports(model, to_json_types, from_json_types)
    boilerplate = BOILERPLATE.format(
        service_imports="".join(f"    {n},\n" for n in service_imports),
        func_imports=func_imports,
    )
    blocks = [(DOC.format(source=source_rel) + boilerplate).rstrip()]
    for op in model.operations:
        blocks.append("\n".join(_render_operation(op)))
    return "\n\n\n".join(blocks).rstrip() + "\n"


def _operation_type_names(operations: tuple[OperationSpec, ...]) -> set[str]:
    names: set[str] = set()
    for op in operations:
        names.add(op.request_schema)
        names.add(op.response_schema)
    return names


def _is_patch_style(model: ClientModel, type_name: str) -> bool:
    for obj in model.objects:
        if obj.name == type_name:
            return not all(field.required for field in obj.fields)
    return False


def _render_func_imports(
    model: ClientModel, to_json_types: set[str], from_json_types: set[str]
) -> str:
    """Each needed func comes from serialization.py or serialization_patch.py (its bucket)."""
    required_funcs: list[str] = []
    patch_funcs: list[str] = []
    for name in to_json_types:
        func = f"{pascal_to_snake(name)}_to_json"
        (patch_funcs if _is_patch_style(model, name) else required_funcs).append(func)
    for name in from_json_types:
        func = f"{pascal_to_snake(name)}_from_json"
        (patch_funcs if _is_patch_style(model, name) else required_funcs).append(func)
    lines = []
    if required_funcs:
        body = "".join(f"    {n},\n" for n in sorted(required_funcs))
        lines.append(f"from argus_collector.api_client.serialization import (\n{body})")
    if patch_funcs:
        body = "".join(f"    {n},\n" for n in sorted(patch_funcs))
        lines.append(f"from argus_collector.api_client.serialization_patch import (\n{body})")
    return "\n".join(lines)


def _render_operation(op: OperationSpec) -> list[str]:
    to_json = f"{pascal_to_snake(op.request_schema)}_to_json"
    from_json = f"{pascal_to_snake(op.response_schema)}_from_json"
    return [
        f"def {op.operation_id}(",
        "    base_url: str,",
        "    token: str,",
        f"    request: {op.request_schema},",
        "    *,",
        '    proxy_mode: ProxyMode = "system",',
        "    timeout_s: float = 10.0,",
        f") -> {op.response_schema}:",
        f'    """{op.method.upper()} {op.path} ({op.security_scheme})."""',
        "    status, raw = _post(",
        "        base_url,",
        f"        {op.path!r},",
        "        token,",
        f"        {to_json}(request),",
        "        proxy_mode,",
        "        timeout_s,",
        "    )",
        f"    return {from_json}(_parse_json_body(status, raw))",
    ]
