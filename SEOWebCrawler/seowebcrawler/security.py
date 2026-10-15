"""Validation helpers for URLs that the crawler is allowed to fetch."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit


class UnsafeTargetError(ValueError):
    """Raised when a URL is malformed or targets a restricted network."""


def _is_public_address(address: str) -> bool:
    """Return whether an IP address is globally routable."""
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    return ip.is_global


def validate_target_url(value: str, *, resolve_dns: bool = True) -> str:
    """Return a normalized public HTTP(S) URL or raise ``UnsafeTargetError``.

    Non-standard ports and embedded credentials are rejected. DNS answers are
    checked on every call so redirect destinations receive the same scrutiny.
    """
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise UnsafeTargetError("URL must be a non-empty string under 2048 characters")
    if any(ord(character) < 32 or character.isspace() for character in value):
        raise UnsafeTargetError("URL contains whitespace or control characters")

    try:
        parts = urlsplit(value)
        scheme = parts.scheme.lower()
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise UnsafeTargetError("URL is malformed") from exc

    if scheme != "https" or not hostname:
        raise UnsafeTargetError("Only absolute HTTPS URLs are allowed")
    if parts.username is not None or parts.password is not None:
        raise UnsafeTargetError("URLs containing credentials are not allowed")
    if port is not None and port != 443:
        raise UnsafeTargetError("Only the standard HTTPS port is allowed")

    try:
        normalized_host = hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise UnsafeTargetError("URL hostname is invalid") from exc
    if not normalized_host:
        raise UnsafeTargetError("URL hostname is invalid")

    try:
        ipaddress.ip_address(normalized_host)
        addresses = [normalized_host]
    except ValueError:
        if not resolve_dns:
            addresses = []
        else:
            try:
                addresses = list(
                    dict.fromkeys(
                        result[4][0]
                        for result in socket.getaddrinfo(
                            normalized_host, port or (443 if scheme == "https" else 80)
                        )
                    )
                )
            except OSError as exc:
                raise UnsafeTargetError("URL hostname could not be resolved") from exc
            if not addresses:
                raise UnsafeTargetError("URL hostname has no addresses")

    if any(not _is_public_address(address) for address in addresses):
        raise UnsafeTargetError("Private or reserved network addresses are not allowed")

    netloc_host = f"[{normalized_host}]" if ":" in normalized_host else normalized_host
    normalized_port = port
    if normalized_port == 443:
        normalized_port = None
    netloc = netloc_host if normalized_port is None else f"{netloc_host}:{normalized_port}"
    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))