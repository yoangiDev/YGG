"""Sesiones aiohttp con validación SSL consistente (certifi)."""

import ssl
from typing import Any

import aiohttp
import certifi

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)


def create_secure_session(**kwargs: Any) -> aiohttp.ClientSession:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    return aiohttp.ClientSession(connector=connector, **kwargs)
