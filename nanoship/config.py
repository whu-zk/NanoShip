"""Configuration management for NanoShip."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """NanoShip configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="NANOSHIP_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # LLM Configuration
    llm_provider: str = Field(default="deepseek", description="LLM provider (deepseek, openai, anthropic)")
    llm_api_key: Optional[str] = Field(default=None, description="API key for LLM provider")
    llm_model: str = Field(default="deepseek-chat", description="Model name to use")
    llm_base_url: Optional[str] = Field(default=None, description="Custom base URL for LLM API")

    # SSH Configuration
    ssh_timeout: int = Field(default=30, description="SSH connection timeout in seconds")
    ssh_key_path: Optional[str] = Field(default=None, description="Path to SSH private key")

    # Database
    db_path: str = Field(default="~/.nanoship/nanoship.db", description="Path to SQLite database")

    # Notifications
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL for notifications")
    webhook_type: str = Field(default="discord", description="Webhook type (discord, slack, feishu, dingtalk)")

    # Deployment
    default_deploy_path: str = Field(default="/opt/nanoship", description="Default remote deployment path")
    auto_ssl: bool = Field(default=True, description="Automatically configure SSL with Let's Encrypt")

    @property
    def db_full_path(self) -> Path:
        """Get the full path to the database file."""
        path = Path(self.db_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def config_dir(self) -> Path:
        """Get the configuration directory."""
        path = Path("~/.nanoship").expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path


# Global settings instance
settings = Settings()
