from __future__ import annotations

import re
from pathlib import PurePosixPath

# Allowed uploads for human-readable documents (no executables).
ALLOWED_DOCUMENT_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".doc", ".docx", ".txt"})

# Primary validation is extension + magic bytes; content-type headers are not trusted alone.
_EXTENSION_TO_MEDIA: dict[str, str] = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain; charset=utf-8",
}

_MAGIC_EXPECTATIONS: dict[str, tuple[int, bytes]] = {
    ".pdf": (0, b"%PDF"),
    ".docx": (0, b"PK\x03\x04"),  # ZIP container
    ".txt": (0, b""),  # no strict magic
}

_MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def sanitize_storage_filename(name: str, *, max_length: int = 180) -> str:
    base = PurePosixPath(name or "document").name
    base = re.sub(r"[^\w.\-()+ ]+", "_", base, flags=re.UNICODE).strip("._")
    if not base:
        base = "document"
    if len(base) > max_length:
        stem, dot, ext = base.rpartition(".")
        if dot and ext:
            keep = max_length - len(ext) - 1
            base = f"{stem[: max(1, keep)]}.{ext}"
        else:
            base = base[:max_length]
    return base


def extension_from_filename(filename: str) -> str:
    lower = (filename or "").lower().strip()
    for ext in (".docx", ".pdf", ".doc", ".txt"):
        if lower.endswith(ext):
            return ext
    return ""


def validate_document_upload(
    *,
    filename: str,
    file_bytes: bytes,
    allowed_extensions: frozenset[str] | None = None,
) -> tuple[str, str]:
    """Return (extension, media_type) or raise ValueError."""
    allowed = allowed_extensions or ALLOWED_DOCUMENT_EXTENSIONS
    ext = extension_from_filename(filename)
    if ext not in allowed:
        raise ValueError(f"Unsupported file type. Allowed: {', '.join(sorted(allowed))}")

    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise ValueError("File is too large (max 15MB).")

    magic = _MAGIC_EXPECTATIONS.get(ext)
    if magic and magic[1]:
        offset, expected = magic
        if len(file_bytes) < offset + len(expected) or file_bytes[offset : offset + len(expected)] != expected:
            raise ValueError("File contents do not match the declared document type.")

    # Legacy .doc is OLE compound file — magic D0 CF 11 E0
    if ext == ".doc":
        if len(file_bytes) >= 8 and file_bytes[:8] != b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise ValueError("File contents do not match a legacy Word document.")

    media = _EXTENSION_TO_MEDIA.get(ext, "application/octet-stream")
    return ext, media


def media_type_for_filename(filename: str) -> str:
    ext = extension_from_filename(filename)
    return _EXTENSION_TO_MEDIA.get(ext, "application/octet-stream")
