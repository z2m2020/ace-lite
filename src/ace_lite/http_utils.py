from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_ALLOWED_HTTP_SCHEMES = {"http", "https"}


def safe_urlopen(request: Request, *, timeout: float) -> Any:
    """Open an HTTP(S) request with basic scheme validation.

    Bandit flags ``urllib.request.urlopen`` because it can be used with non-HTTP
    schemes (for example, ``file://``). ACE-Lite only uses it for HTTP(S)
    endpoints, so we validate the request URL scheme here and keep the call
    site centralized.
    """

    full_url = getattr(request, "full_url", None)
    if not full_url:
        try:
            full_url = request.get_full_url()
        except Exception:
            full_url = ""

    parsed = urlparse(str(full_url or ""))
    scheme = parsed.scheme.strip().lower()
    if not scheme:
        raise ValueError("unsupported URL scheme: <missing>")
    if scheme not in _ALLOWED_HTTP_SCHEMES:
        raise ValueError(f"unsupported URL scheme: {scheme}")

    return urlopen(request, timeout=timeout)  # nosec B310


__all__ = ["safe_urlopen"]

