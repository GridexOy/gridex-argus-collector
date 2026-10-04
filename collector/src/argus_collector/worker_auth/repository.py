"""I/O of worker_auth: DPAPI-encrypted token file, plain connection.json.

DPAPI (CryptProtectData/CryptUnprotectData) ties the ciphertext to the
current Windows user; it is not portable and needs no key management (CLAUDE.md
rule 7). Off Windows (tests, CI) there is no DPAPI, so a reversible XOR
obfuscation stands in -- clearly not secure, used only so this module's
logic is testable on Linux; the real path is windows_encrypt/windows_decrypt.
"""

from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path

from argus_collector.runtime import contract as runtime

TOKEN_FILE = "worker_token.bin"
CONNECTION_FILE = "worker_connection.json"
_FALLBACK_XOR = 0x5A


class DpapiError(RuntimeError):
    """CryptProtectData/CryptUnprotectData failed."""


def token_path(data_dir: Path | None = None) -> Path:
    return (data_dir or runtime.user_data_dir()) / TOKEN_FILE


def connection_path(data_dir: Path | None = None) -> Path:
    return (data_dir or runtime.user_data_dir()) / CONNECTION_FILE


def windows_encrypt(data: bytes) -> bytes:
    crypt32 = getattr(ctypes, "windll").crypt32  # noqa: B009 - windll exists only on Windows
    kernel32 = getattr(ctypes, "windll").kernel32  # noqa: B009
    blob_in = _blob(data)
    blob_out = _Blob()
    if not crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise DpapiError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def windows_decrypt(data: bytes) -> bytes:
    crypt32 = getattr(ctypes, "windll").crypt32  # noqa: B009
    kernel32 = getattr(ctypes, "windll").kernel32  # noqa: B009
    blob_in = _blob(data)
    blob_out = _Blob()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise DpapiError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _fallback_obfuscate(data: bytes) -> bytes:
    return bytes(b ^ _FALLBACK_XOR for b in data)


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _Blob:
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def save_token(token: str, data_dir: Path | None = None, windows: bool | None = None) -> None:
    on_windows = windows if windows is not None else os.name == "nt"
    raw = token.encode("utf-8")
    encrypted = windows_encrypt(raw) if on_windows else _fallback_obfuscate(raw)
    path = token_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encrypted)


def load_token(data_dir: Path | None = None, windows: bool | None = None) -> str | None:
    on_windows = windows if windows is not None else os.name == "nt"
    path = token_path(data_dir)
    if not path.is_file():
        return None
    encrypted = path.read_bytes()
    try:
        raw = windows_decrypt(encrypted) if on_windows else _fallback_obfuscate(encrypted)
    except (DpapiError, OSError, ValueError):
        return None
    return raw.decode("utf-8", errors="replace")


def clear_token(data_dir: Path | None = None) -> None:
    token_path(data_dir).unlink(missing_ok=True)


def save_connection_mapping(mapping: dict[str, str], data_dir: Path | None = None) -> None:
    path = connection_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping), encoding="utf-8")


def load_connection_mapping(data_dir: Path | None = None) -> dict[str, object] | None:
    path = connection_path(data_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None
