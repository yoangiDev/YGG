"""Utilities for aiohttp sessions with consistent SSL certificate validation."""

import aiohttp
import ssl
import certifi

_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)


def create_secure_session(*args, **kwargs):
    """Create an aiohttp ClientSession with a certifi-backed SSL context."""
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    if "timeout" not in kwargs:
        kwargs["timeout"] = _DEFAULT_TIMEOUT
    return aiohttp.ClientSession(connector=connector, *args, **kwargs)

