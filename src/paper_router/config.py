from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


_PROVIDER_ENV_VARS: dict[str, str] = {
    "semantic_scholar": "SEMANTIC_SCHOLAR_API_KEY",
    "openalex": "OPENALEX_API_KEY",
    "crossref": "CROSSREF_API_KEY",
    "arxiv": "ARXIV_API_KEY",
}


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for a single paper provider."""
    api_key: str | None = None


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration."""
    semantic_scholar: ProviderConfig = field(default_factory=ProviderConfig)
    openalex: ProviderConfig = field(default_factory=ProviderConfig)
    crossref: ProviderConfig = field(default_factory=ProviderConfig)
    arxiv: ProviderConfig = field(default_factory=ProviderConfig)


def load_dotenv(dotenv_path: str | None = None) -> None:
    """Parse .env file and load variables into os.environ.

    Existing env vars are never overridden. Idempotent: only loads once
    per process when called without an explicit path (the normal case).
    Passing an explicit path always attempts loading (for testing).
    """
    path: Path
    if dotenv_path is not None:
        path = Path(dotenv_path)
    else:
        path = Path.cwd() / ".env"
        if hasattr(load_dotenv, "_loaded"):
            return

    if not path.is_file():
        return
    if dotenv_path is None:
        load_dotenv._loaded = True  # type: ignore[attr-defined]

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]

        if key and key not in os.environ:
            os.environ[key] = value


def load_config(*, _dotenv_path: str | None = None) -> AppConfig:
    """Load application configuration from environment variables.

    Automatically loads .env from CWD on first call. Environment variables
    always take precedence over .env values.

    The _dotenv_path parameter is for testing only.
    """
    load_dotenv(_dotenv_path)

    provider_configs: dict[str, ProviderConfig] = {}
    for field_name, env_var in _PROVIDER_ENV_VARS.items():
        raw = os.environ.get(env_var)
        api_key: str | None = raw if raw else None
        provider_configs[field_name] = ProviderConfig(api_key=api_key)

    return AppConfig(**provider_configs)
