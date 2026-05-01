from __future__ import annotations

import os
from pathlib import Path

import pytest

from paper_router.config import AppConfig, ProviderConfig, load_config, load_dotenv


class TestLoadDotenv:
    def test_loads_simple_key_value(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        dotenv = tmp_path / ".env"
        dotenv.write_text("SEMANTIC_SCHOLAR_API_KEY=mykey123\n", encoding="utf-8")
        monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
        load_dotenv(str(dotenv))
        assert os.environ["SEMANTIC_SCHOLAR_API_KEY"] == "mykey123"

    def test_missing_file_is_noop(self) -> None:
        load_dotenv("/nonexistent/path/.env")

    def test_does_not_override_existing_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        dotenv = tmp_path / ".env"
        dotenv.write_text("MY_VAR=from_dotenv\n", encoding="utf-8")
        monkeypatch.setenv("MY_VAR", "from_env")
        load_dotenv(str(dotenv))
        assert os.environ["MY_VAR"] == "from_env"

    def test_strips_quotes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        dotenv = tmp_path / ".env"
        dotenv.write_text('MY_KEY="quoted value"\n', encoding="utf-8")
        monkeypatch.delenv("MY_KEY", raising=False)
        load_dotenv(str(dotenv))
        assert os.environ["MY_KEY"] == "quoted value"

    def test_ignores_comments_and_blanks(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        dotenv = tmp_path / ".env"
        dotenv.write_text("# comment\n\n\nAPI_KEY=real_key\n", encoding="utf-8")
        monkeypatch.delenv("API_KEY", raising=False)
        load_dotenv(str(dotenv))
        assert os.environ["API_KEY"] == "real_key"

    def test_handles_empty_value(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        dotenv = tmp_path / ".env"
        dotenv.write_text("API_KEY=\n", encoding="utf-8")
        monkeypatch.delenv("API_KEY", raising=False)
        # Clear provider env vars that may have been set by other tests
        monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
        load_dotenv(str(dotenv))
        assert os.environ["API_KEY"] == ""
        # Empty string should be normalized to None by load_config
        assert load_config().semantic_scholar.api_key is None


class TestProviderConfig:
    def test_default_api_key_is_none(self) -> None:
        assert ProviderConfig().api_key is None

    def test_frozen(self) -> None:
        with pytest.raises(AttributeError):
            ProviderConfig(api_key="x").api_key = "y"  # type: ignore[misc]


class TestAppConfig:
    def test_all_defaults_are_none(self) -> None:
        cfg = AppConfig()
        assert cfg.semantic_scholar.api_key is None
        assert cfg.openalex.api_key is None
        assert cfg.crossref.api_key is None
        assert cfg.arxiv.api_key is None

    def test_frozen(self) -> None:
        with pytest.raises(AttributeError):
            AppConfig().semantic_scholar = ProviderConfig()  # type: ignore[misc]

    def test_providers_are_independent(self) -> None:
        cfg = AppConfig(semantic_scholar=ProviderConfig(api_key="ss_key"))
        assert cfg.semantic_scholar.api_key == "ss_key"
        assert cfg.openalex.api_key is None


class TestLoadConfig:
    def test_defaults_when_no_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in ("SEMANTIC_SCHOLAR_API_KEY", "OPENALEX_API_KEY", "CROSSREF_API_KEY", "ARXIV_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        cfg = load_config()
        assert cfg.semantic_scholar.api_key is None

    def test_reads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "ss-secret")
        monkeypatch.setenv("OPENALEX_API_KEY", "oa-secret")
        monkeypatch.setenv("CROSSREF_API_KEY", "cr-secret")
        monkeypatch.setenv("ARXIV_API_KEY", "ar-secret")
        cfg = load_config()
        assert cfg.semantic_scholar.api_key == "ss-secret"
        assert cfg.openalex.api_key == "oa-secret"
        assert cfg.crossref.api_key == "cr-secret"
        assert cfg.arxiv.api_key == "ar-secret"
