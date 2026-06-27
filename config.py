"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration for the Telegram quiz bot."""

    bot_token: str
    channel_id: int | str
    admin_id: int
    database_path: str = "quiz.db"
    quiz_duration_seconds: int = 300


def _required(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigError(f"Missing required environment variable: {name}")
    return value.strip()


def _parse_admin_id(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError("ADMIN_ID must be a numeric Telegram user ID") from exc


def _parse_channel_id(value: str) -> int | str:
    """Return a numeric channel ID when possible, otherwise a @username string."""
    try:
        return int(value)
    except ValueError:
        if value.startswith("@") and len(value) > 1:
            return value
        raise ConfigError("CHANNEL_ID must be a numeric channel ID or @channelusername")


def load_config() -> Config:
    """Load and validate configuration from process environment."""
    return Config(
        bot_token=_required("BOT_TOKEN"),
        channel_id=_parse_channel_id(_required("CHANNEL_ID")),
        admin_id=_parse_admin_id(_required("ADMIN_ID")),
        database_path=os.getenv("DATABASE_PATH", "quiz.db").strip() or "quiz.db",
    )


CONFIG: Final[Config] = load_config()
