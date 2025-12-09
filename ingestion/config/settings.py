"""Ingestion pipeline configuration."""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import json
import yaml
from pathlib import Path


@dataclass
class IngestionConfig:
    """Configuration for the ingestion pipeline.
    
    Can be loaded from JSON or YAML files.
    """
    
    # Source settings
    source_path: str = ""
    recursive: bool = True
    
    # Processing settings
    pages_to_read: int = 3
    temp_dir: Optional[str] = None
    
    # Classifier settings
    classifier_type: str = "openai"  # openai, anthropic, ollama
    classifier_model: str = ""
    classifier_api_key: Optional[str] = None
    
    # Handler settings
    handler_type: str = "s3"  # s3, api
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    
    # Reader settings
    reader_type: str = "pymupdf"  # pymupdf, pdfplumber
    
    # Storage provider (for S3 source and handler)
    storage_provider: str = "aws"  # aws, gcs, etc.
    storage_credentials: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_json(cls, file_path: str) -> 'IngestionConfig':
        """Load configuration from JSON file.
        
        Args:
            file_path: Path to JSON configuration file
            
        Returns:
            IngestionConfig instance
        """
        with open(file_path, 'r') as f:
            data = json.load(f)
        return cls(**data)
    
    @classmethod
    def from_yaml(cls, file_path: str) -> 'IngestionConfig':
        """Load configuration from YAML file.
        
        Args:
            file_path: Path to YAML configuration file
            
        Returns:
            IngestionConfig instance
        """
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        return cls(**data)
    
    @classmethod
    def from_env(cls) -> 'IngestionConfig':
        """Load configuration from environment variables.
        
        Returns:
            IngestionConfig instance
        """
        return cls(
            source_path=os.getenv('INGESTION_SOURCE_PATH', ''),
            recursive=os.getenv('INGESTION_RECURSIVE', 'true').lower() == 'true',
            pages_to_read=int(os.getenv('INGESTION_PAGES_TO_READ', '3')),
            temp_dir=os.getenv('INGESTION_TEMP_DIR'),
            classifier_type=os.getenv('INGESTION_CLASSIFIER_TYPE', 'openai'),
            classifier_model=os.getenv('INGESTION_CLASSIFIER_MODEL', ''),
            classifier_api_key=os.getenv('INGESTION_CLASSIFIER_API_KEY'),
            handler_type=os.getenv('INGESTION_HANDLER_TYPE', 's3'),
            api_base_url=os.getenv('INGESTION_API_BASE_URL'),
            api_key=os.getenv('INGESTION_API_KEY'),
            reader_type=os.getenv('INGESTION_READER_TYPE', 'pymupdf'),
            storage_provider=os.getenv('INGESTION_STORAGE_PROVIDER', 'aws'),
        )
    
    def save_json(self, file_path: str) -> None:
        """Save configuration to JSON file.
        
        Args:
            file_path: Path to save configuration
        """
        data = {
            'source_path': self.source_path,
            'recursive': self.recursive,
            'pages_to_read': self.pages_to_read,
            'temp_dir': self.temp_dir,
            'classifier_type': self.classifier_type,
            'classifier_model': self.classifier_model,
            'handler_type': self.handler_type,
            'api_base_url': self.api_base_url,
            'reader_type': self.reader_type,
            'storage_provider': self.storage_provider,
            'storage_credentials': self.storage_credentials,
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def save_yaml(self, file_path: str) -> None:
        """Save configuration to YAML file.
        
        Args:
            file_path: Path to save configuration
        """
        data = {
            'source_path': self.source_path,
            'recursive': self.recursive,
            'pages_to_read': self.pages_to_read,
            'temp_dir': self.temp_dir,
            'classifier_type': self.classifier_type,
            'classifier_model': self.classifier_model,
            'handler_type': self.handler_type,
            'api_base_url': self.api_base_url,
            'reader_type': self.reader_type,
            'storage_provider': self.storage_provider,
            'storage_credentials': self.storage_credentials,
        }
        
        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

