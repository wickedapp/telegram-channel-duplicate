import os
import re
import logging
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class Config:
    """Configuration loader for Telegram Channel Duplicator."""

    def __init__(self, config_path: str = "config.yaml"):
        # Load environment variables
        load_dotenv()

        self.api_id = os.getenv("API_ID")
        self.api_hash = os.getenv("API_HASH")
        self.phone_number = os.getenv("PHONE_NUMBER")

        if not self.api_id or not self.api_hash:
            raise ValueError(
                "API_ID and API_HASH must be set in .env file. "
                "Get them from https://my.telegram.org"
            )

        self.api_id = int(self.api_id)

        # Load YAML config
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_file, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        self._validate_config()
        self._setup_logging()

    def _validate_config(self) -> None:
        """Validate required configuration fields."""
        required = ["target_channel", "source_channels"]
        for field in required:
            if field not in self._config:
                raise ValueError(f"Missing required config field: {field}")

        if not self._config["source_channels"]:
            raise ValueError("At least one source channel is required")

    def _setup_logging(self) -> None:
        """Setup logging based on config."""
        log_level = self._config.get("log_level", "INFO")
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    @property
    def target_channel(self) -> str:
        """Target channel to post to."""
        return self._config["target_channel"]

    @property
    def source_channels(self) -> list[str]:
        """List of source channels to monitor."""
        return self._config["source_channels"]

    @property
    def my_channel_name(self) -> str:
        """Your channel name for replacements."""
        return self._config.get("my_channel_name", "")

    @property
    def my_username(self) -> str:
        """Your username for replacements."""
        return self._config.get("my_username", "")

    @property
    def my_contact_username(self) -> str:
        """Your contact username for replacements."""
        return self._config.get("my_contact_username", "")

    @property
    def replacements(self) -> list[dict[str, str]]:
        """Text replacement rules."""
        return self._config.get("replacements", [])

    @property
    def negative_keywords(self) -> list[str]:
        """Keywords that trigger message filtering."""
        filters = self._config.get("negative_filters", {})
        return filters.get("keywords", [])

    @property
    def negative_patterns(self) -> list[str]:
        """Regex patterns that trigger message filtering."""
        filters = self._config.get("negative_filters", {})
        return filters.get("patterns", [])

    @property
    def ignore_forwarded(self) -> bool:
        """Whether to ignore forwarded messages."""
        filters = self._config.get("message_filters", {})
        return filters.get("ignore_forwarded", True)

    @property
    def min_length(self) -> int:
        """Minimum message length."""
        filters = self._config.get("message_filters", {})
        return filters.get("min_length", 0)

    @property
    def max_length(self) -> int:
        """Maximum message length (0 = no limit)."""
        filters = self._config.get("message_filters", {})
        return filters.get("max_length", 0)

    def get_template_vars(self) -> dict[str, str]:
        """Get template variables for text replacement."""
        return {
            "my_channel_name": self.my_channel_name,
            "my_username": self.my_username,
            "my_contact_username": self.my_contact_username,
        }
