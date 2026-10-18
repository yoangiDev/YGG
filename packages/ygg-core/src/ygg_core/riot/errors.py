"""Riot client errors.

They inherit from ValueError / ConnectionError so that code that already caught
those exceptions keeps working.
"""


class RiotError(Exception):
    pass


class RiotNotFoundError(RiotError, ValueError):
    pass


class RiotUnavailableError(RiotError, ConnectionError):
    pass
