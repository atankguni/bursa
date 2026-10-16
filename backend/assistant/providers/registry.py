"""
assistant/providers/registry.py
-------------------------------
Resolves `settings.assistant_chain` ("provider:model" entries, tried in order)
into configured adapters. Unknown providers are logged and skipped; providers
without credentials are skipped silently, so the chain can list fallbacks that
only activate once their key is added.
"""

import logging

from assistant.providers.base import ChatProvider
from assistant.providers.gemini import GeminiProvider
from config import settings

log = logging.getLogger("bursa.assistant.registry")

# name -> adapter class. Add new providers here.
_REGISTRY: dict[str, type[ChatProvider]] = {
    GeminiProvider.name: GeminiProvider,
}


def parse_entry(entry: str) -> tuple[str, str]:
    name, sep, model = entry.partition(":")
    if not sep or not name.strip() or not model.strip():
        raise ValueError(f"assistant_chain entry {entry!r} must look like 'provider:model'")
    return name.strip(), model.strip()


def resolve_chain() -> list[tuple[ChatProvider, str]]:
    """Configured (adapter, model) attempts, in order."""
    instances: dict[str, ChatProvider | None] = {}
    attempts: list[tuple[ChatProvider, str]] = []
    for entry in settings.assistant_chain:
        try:
            name, model = parse_entry(entry)
        except ValueError as exc:
            log.warning("%s", exc)
            continue
        cls = _REGISTRY.get(name)
        if cls is None:
            log.warning("Unknown assistant provider %r (known: %s)", name, sorted(_REGISTRY))
            continue
        if name not in instances:
            instances[name] = cls.from_settings(settings)
        provider = instances[name]
        if provider is not None:
            attempts.append((provider, model))
    return attempts


def setup_hint() -> str:
    """What to set to enable the providers named in the chain."""
    names: list[str] = []
    for entry in settings.assistant_chain:
        try:
            name, _ = parse_entry(entry)
        except ValueError:
            continue
        cls = _REGISTRY.get(name)
        if cls is not None and cls.credential_env not in names:
            names.append(cls.credential_env)
    return " or ".join(names) or "an assistant provider in assistant_chain"
