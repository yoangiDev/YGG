"""Errores del cliente de Riot.

Heredan de ValueError / ConnectionError para que el código que ya capturaba
esas excepciones siga funcionando.
"""


class RiotError(Exception):
    pass


class RiotNotFoundError(RiotError, ValueError):
    pass


class RiotUnavailableError(RiotError, ConnectionError):
    pass
