"""Configuration: configs/default.yaml, overridden by VOXELTRACE_* environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import SecretStr, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "default.yaml"


def workspace_root() -> Path:
    """Where VoxelTrace data and outputs live by default: $VOXELTRACE_WORKSPACE if set; the
    parent of a source checkout (development layout); otherwise the current directory. An
    installed package never points into site-packages."""
    import os

    env = os.environ.get("VOXELTRACE_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()
    if (REPO_ROOT / "pyproject.toml").exists() and (REPO_ROOT / "src" / "voxeltrace").is_dir():
        return REPO_ROOT.parent.resolve()
    return Path.cwd().resolve()


LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def is_loopback_url(url: str) -> bool:
    return urlparse(url).hostname in LOOPBACK_HOSTS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VOXELTRACE_",
        yaml_file=DEFAULT_CONFIG_PATH,
        extra="ignore",
    )

    ai_base_url: str = "http://127.0.0.1:8000/v1"
    ai_model: str | None = None
    ai_timeout_s: float = 5.0
    ai_allow_remote: bool = False
    # Optional: a local server may be started with --api-key. Never required.
    ai_api_key: SecretStr | None = None

    data_dir: Path = Path("../data")
    models_dir: Path = Path("../models")
    outputs_dir: Path = Path("../outputs")
    logs_dir: Path = Path("../logs")
    tmp_dir: Path = Path("../tmp")

    @model_validator(mode="after")
    def _check_endpoint(self) -> Settings:
        scheme = urlparse(self.ai_base_url).scheme
        if scheme not in {"http", "https"}:
            raise ValueError(f"ai_base_url must be http(s), got {self.ai_base_url!r}")
        if not self.ai_allow_remote and not is_loopback_url(self.ai_base_url):
            raise ValueError(
                f"ai_base_url {self.ai_base_url!r} is not a loopback address; "
                "VoxelTrace is local-only by default (set ai_allow_remote to override)."
            )
        return self

    def resolve(self, path: Path) -> Path:
        """Resolve a configured path relative to the repository root."""
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, env_settings, YamlConfigSettingsSource(settings_cls))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
