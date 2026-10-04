"""A small multipart/form-data splitter (stdlib only, binary safe).

Splits the body on the boundary from the Content-Type header and parses each
part's headers with `email`; part bodies are returned byte for byte.
"""

from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from email.parser import BytesHeaderParser
from email.utils import collapse_rfc2231_value

from contract_server.errors import invalid


@dataclass(frozen=True)
class Part:
    name: str
    filename: str | None
    content_type: str
    data: bytes


def boundary_of(content_type: str) -> str:
    message = Message()
    message["content-type"] = content_type
    if message.get_content_type() != "multipart/form-data":
        raise invalid("body must be multipart/form-data")
    boundary = message.get_param("boundary")
    if not isinstance(boundary, str) or not boundary:
        raise invalid("multipart/form-data without a boundary")
    return boundary


def _param(headers: Message, name: str) -> str | None:
    value = headers.get_param(name, header="content-disposition")
    if value is None:
        return None
    return collapse_rfc2231_value(value)


def _parse_part(chunk: bytes) -> Part:
    if chunk.startswith(b"\r\n"):
        chunk = chunk[2:]
    head, separator, data = chunk.partition(b"\r\n\r\n")
    if not separator:
        raise invalid("multipart part without a header block")
    if data.endswith(b"\r\n"):
        data = data[:-2]
    headers = BytesHeaderParser().parsebytes(head + b"\r\n\r\n")
    name = _param(headers, "name")
    if not name:
        raise invalid("multipart part without a form field name")
    content_type = headers.get_content_type() if headers.get("content-type") else ""
    return Part(name, _param(headers, "filename"), content_type, data)


def parse(content_type: str, body: bytes) -> dict[str, Part]:
    """Form fields by name; 400 invalid_input when the body is not valid multipart."""
    delimiter = b"--" + boundary_of(content_type).encode("latin-1")
    chunks = body.split(delimiter)
    if len(chunks) < 3:
        raise invalid("malformed multipart body")
    parts: dict[str, Part] = {}
    for chunk in chunks[1:]:
        if chunk.startswith(b"--"):
            return parts
        part = _parse_part(chunk)
        parts[part.name] = part
    raise invalid("multipart body without a closing boundary")
