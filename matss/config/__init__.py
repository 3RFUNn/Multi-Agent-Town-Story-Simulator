"""Data-driven, validated content (replaces the hardcoded ``config.py`` dicts).

``load_content()`` reads ``matss/content/world.json`` (or any path/dict),
validates it against :mod:`matss.config.schema`, and returns a :class:`Content`
object exposing typed domain objects (``NavGrid``, ``Place``, ``AgentDef`` …).
"""

from .schema import ContentError, validate_content
from .loader import Content, load_content, DEFAULT_CONTENT_PATH
from .env import load_dotenv, resolve_api_key, find_dotenv, parse_dotenv

__all__ = [
    "ContentError", "validate_content", "Content", "load_content",
    "DEFAULT_CONTENT_PATH",
    "load_dotenv", "resolve_api_key", "find_dotenv", "parse_dotenv",
]
