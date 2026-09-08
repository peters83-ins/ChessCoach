"""Lazy SDK construction only. No coaching requests are implemented yet."""

from typing import TYPE_CHECKING

from chesscoach.config import Settings

if TYPE_CHECKING:
    from openai import OpenAI


def create_client(settings: Settings) -> "OpenAI":
    """Validate explicit configuration and construct a client without an API call.

    The eventual coaching service owns this client's lifetime and must close it.
    The desktop launch path deliberately does not call this function.
    """
    settings.require_ai()
    from openai import OpenAI

    return OpenAI(api_key=settings.openai_api_key)
