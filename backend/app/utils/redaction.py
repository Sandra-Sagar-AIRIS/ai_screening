from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def redact_database_url(url: str) -> str:
    """
    Redact credentials from a database URL while preserving useful diagnostics.

    Example:
    postgresql+psycopg://user:password@host:5432/db
    -> postgresql+psycopg://user:****@host:5432/db
    """
    if not url:
        return url

    try:
        parsed = urlsplit(url)
    except Exception:
        return "<redacted-db-url>"

    username = parsed.username
    password = parsed.password
    hostname = parsed.hostname
    port = parsed.port

    if username is None and password is None:
        return url

    user_part = username or "****"
    pass_part = "****" if password is not None else ""
    auth_part = f"{user_part}:{pass_part}" if pass_part else user_part

    host_part = hostname or ""
    if port is not None:
        host_part = f"{host_part}:{port}"
    if parsed.netloc.startswith("[") and hostname and ":" in hostname:
        host_part = f"[{hostname}]"
        if port is not None:
            host_part = f"{host_part}:{port}"

    netloc = f"{auth_part}@{host_part}" if host_part else auth_part
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))

