"""Render api_client/repository.py: the stdlib `urllib.request` HTTP transport.

Fixed boilerplate (openers, ApiError, the JSON and multipart POST helpers,
error parsing); only the error schema's class/codec and their import lines
vary with the model.
"""

from __future__ import annotations

from codegen.chunking import Needs, local_imports, render_module
from codegen.pytypes import codec_name
from codegen.types import ClientModel

DOC = '''"""Generated HTTP transport for the api_client module (mechanically generated).

Source: {source}.
Do not edit by hand -- see api_client/README.md to regenerate.
stdlib-only `urllib.request`, no third-party dependency. `proxy_mode="system"`
honors the OS proxy configuration (needed for the real ARGUS host,
ARGUS20_TZ_TANDEM.md pair A1 item 4); `proxy_mode="direct"` never uses a
proxy (needed against loopback/contract_server, where the Windows system
proxy answers 127.0.0.1 with a 502 -- see ARGUS20_COLLECTOR_CHANGELOG.md,
commit 6b6467b). The caller decides the mode; this module never inspects
the target host to guess it -- that is config-reading, a different module's job.
"""'''
BODY = '''SYSTEM_OPENER = urllib.request.build_opener()
DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({{}}))
ProxyMode = Literal["system", "direct"]
_T = TypeVar("_T")


class ApiError(RuntimeError):
    """A non-2xx response, a 2xx one whose body did not parse, or no response at
    all (status 0: refused, unresolvable, timed out). `error` is the parsed
    {error} body when the server sent one; `raw` is the body (or the network
    error) text, at most 300 characters."""

    def __init__(
        self, status: int, error: {error} | None, retry_after: str | None, raw: str
    ) -> None:
        detail = error.detail if error is not None else raw[:300]
        super().__init__(f"HTTP {{status}}: {{detail}}")
        self.status = status
        self.error = error
        self.retry_after = retry_after
        self.raw = raw


def path_param(value: str) -> str:
    """Percent-encode one path segment; a `/` inside the value is encoded too."""
    return urllib.parse.quote(value, safe="")


def post_json(
    base_url: str,
    path: str,
    token: str,
    body: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    proxy_mode: ProxyMode,
    timeout_s: float,
) -> tuple[int, bytes]:
    data = json.dumps(body).encode("utf-8")
    return _post(base_url, path, token, data, "application/json", headers, proxy_mode, timeout_s)


def post_multipart(
    base_url: str,
    path: str,
    token: str,
    parts: list[Part],
    *,
    headers: dict[str, str] | None = None,
    proxy_mode: ProxyMode,
    timeout_s: float,
) -> tuple[int, bytes]:
    boundary = new_boundary(parts)
    data = encode_multipart(parts, boundary)
    content_type = f"multipart/form-data; boundary={{boundary}}"
    return _post(base_url, path, token, data, content_type, headers, proxy_mode, timeout_s)


def parse_response(status: int, raw: bytes, parse: Callable[[dict[str, Any]], _T]) -> _T:
    """Parse a 2xx body with the success schema; a mismatching body raises ApiError."""
    data = _json_object(status, raw)
    try:
        return parse(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise ApiError(status, None, None, f"unexpected body: {{exc!r}}"[:300]) from exc


def _opener(proxy_mode: ProxyMode) -> urllib.request.OpenerDirector:
    return DIRECT_OPENER if proxy_mode == "direct" else SYSTEM_OPENER


def _post(
    base_url: str,
    path: str,
    token: str,
    data: bytes,
    content_type: str,
    headers: dict[str, str] | None,
    proxy_mode: ProxyMode,
    timeout_s: float,
) -> tuple[int, bytes]:
    url = base_url.rstrip("/") + path
    all_headers = {{
        "Content-Type": content_type,
        "Accept": "application/json",
        "Authorization": f"Bearer {{token}}",
        **(headers or {{}}),
    }}
    request = urllib.request.Request(url, data=data, headers=all_headers, method="POST")
    try:
        with _opener(proxy_mode).open(request, timeout=timeout_s) as response:
            return int(response.status), bytes(response.read())
    except urllib.error.HTTPError as exc:
        raise _api_error_from_http(exc) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ApiError(0, None, None, f"{{url}}: {{exc}}"[:300]) from exc


def _api_error_from_http(exc: urllib.error.HTTPError) -> ApiError:
    raw = exc.read().decode("utf-8", errors="replace")
    retry_after = exc.headers.get("Retry-After") if exc.headers is not None else None
    parsed: {error} | None = None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            parsed = {error_from_json}(data)
    except (ValueError, KeyError, TypeError):
        parsed = None
    return ApiError(exc.code, parsed, retry_after, raw[:300])


def _json_object(status: int, raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise ApiError(status, None, None, f"not JSON: {{raw[:120]!r}}") from exc
    if not isinstance(data, dict):
        raise ApiError(status, None, None, f"not a JSON object: {{raw[:120]!r}}")
    return data'''
PLAIN_IMPORTS = ("json", "urllib.error", "urllib.parse", "urllib.request")
STDLIB = {("collections.abc", "Callable"), *(("typing", n) for n in ("Any", "Literal", "TypeVar"))}
MULTIPART = {("multipart", name) for name in ("Part", "encode_multipart", "new_boundary")}


def render_repository(
    model: ClientModel, source: str, type_owner: dict[str, str], codec_owner: dict[str, str]
) -> str:
    error, error_from_json = model.error_schema, codec_name(model.error_schema, "from")
    needs = Needs(stdlib=set(STDLIB), types={error}, codecs={error_from_json}, fixed=set(MULTIPART))
    local = local_imports(needs, set(), type_owner, codec_owner)
    body = BODY.format(error=error, error_from_json=error_from_json).splitlines()
    return render_module(DOC.format(source=source), needs, local, body, PLAIN_IMPORTS)
