"""Ingestion pipeline configuration."""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import yaml
from ingestion.env import API_BASE_URL, READER_TYPE, TEMP_DIR


@dataclass
class IngestionConfig:
    """Configuration for the ingestion pipeline.

    Uses environment variables from env.py as defaults.
    Can be loaded from JSON or YAML files.
    """

    # Source settings
    source_path: str = ""
    recursive: bool = True

    # Processing settings
    pages_to_read: int = 3
    temp_dir: Optional[str] = field(default_factory=lambda: TEMP_DIR)
    reader_type: str = field(default_factory=lambda: READER_TYPE)
    api_base_url: str = field(default_factory=lambda: API_BASE_URL)

    # Storage provider (for S3 source and handler)
    storage_provider: str = "aws"  # aws, gcs, etc.
    storage_credentials: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, file_path: str) -> "IngestionConfig":
        """Load configuration from JSON file.

        Args:
            file_path: Path to JSON configuration file

        Returns:
            IngestionConfig instance
        """
        with open(file_path, "r") as f:
            data = json.load(f)
        return cls(**data)

    @classmethod
    def from_yaml(cls, file_path: str) -> "IngestionConfig":
        """Load configuration from YAML file.

        Args:
            file_path: Path to YAML configuration file

        Returns:
            IngestionConfig instance
        """
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def __post_init__(self):
        """Normalize string fields to avoid subtle whitespace issues."""
        fields_to_strip = [
            "source_path",
            "temp_dir",
            "reader_type",
            "api_base_url",
            "storage_provider",
        ]
        for name in fields_to_strip:
            value = getattr(self, name, None)
            if isinstance(value, str):
                setattr(self, name, value.strip())

    def save_json(self, file_path: str) -> None:
        """Save configuration to JSON file.

        Args:
            file_path: Path to save configuration
        """
        data = {
            "source_path": self.source_path,
            "recursive": self.recursive,
            "pages_to_read": self.pages_to_read,
            "temp_dir": self.temp_dir,
            "reader_type": self.reader_type,
            "api_base_url": self.api_base_url,
            "storage_provider": self.storage_provider,
            "storage_credentials": self.storage_credentials,
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def save_yaml(self, file_path: str) -> None:
        """Save configuration to YAML file.

        Args:
            file_path: Path to save configuration
        """
        data = {
            "source_path": self.source_path,
            "recursive": self.recursive,
            "pages_to_read": self.pages_to_read,
            "temp_dir": self.temp_dir,
            "reader_type": self.reader_type,
            "api_base_url": self.api_base_url,
            "storage_provider": self.storage_provider,
            "storage_credentials": self.storage_credentials,
        }

        with open(file_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
