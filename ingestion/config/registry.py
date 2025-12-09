"""Catalog registry for managing document collections."""

import json
import yaml
from typing import List, Optional, Dict, Any
from pathlib import Path
from ..core.models import Catalog


class CatalogRegistry:
    """Manage catalog definitions and provide CRUD operations.
    
    Catalogs can be loaded from and saved to JSON or YAML files.
    """

    def __init__(self):
        """Initialize empty catalog registry."""
        self.catalogs: List[Catalog] = []

    def add_catalog(self, catalog: Catalog) -> None:
        """Add a catalog to the registry.
        
        Args:
            catalog: Catalog to add
            
        Raises:
            ValueError: If catalog with same ID already exists
        """
        if self.get_by_id(catalog.id):
            raise ValueError(f"Catalog with ID '{catalog.id}' already exists")
        self.catalogs.append(catalog)

    def remove_catalog(self, catalog_id: str) -> bool:
        """Remove a catalog from the registry.
        
        Args:
            catalog_id: ID of catalog to remove
            
        Returns:
            True if removed, False if not found
        """
        original_length = len(self.catalogs)
        self.catalogs = [c for c in self.catalogs if c.id != catalog_id]
        return len(self.catalogs) < original_length

    def update_catalog(self, catalog: Catalog) -> bool:
        """Update an existing catalog.
        
        Args:
            catalog: Updated catalog
            
        Returns:
            True if updated, False if not found
        """
        for i, c in enumerate(self.catalogs):
            if c.id == catalog.id:
                self.catalogs[i] = catalog
                return True
        return False

    def get_by_id(self, catalog_id: str) -> Optional[Catalog]:
        """Get a catalog by its ID.
        
        Args:
            catalog_id: ID of catalog to find
            
        Returns:
            Catalog if found, None otherwise
        """
        for catalog in self.catalogs:
            if catalog.id == catalog_id:
                return catalog
        return None

    def get_all(self) -> List[Catalog]:
        """Get all catalogs.
        
        Returns:
            List of all catalogs
        """
        return self.catalogs.copy()

    def clear(self) -> None:
        """Remove all catalogs."""
        self.catalogs.clear()

    def load_from_json(self, file_path: str) -> None:
        """Load catalogs from a JSON file.
        
        Args:
            file_path: Path to JSON file
        """
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        self.clear()
        catalogs_data = data.get('catalogs', [])
        
        for catalog_data in catalogs_data:
            catalog = Catalog(**catalog_data)
            self.catalogs.append(catalog)

    def load_from_yaml(self, file_path: str) -> None:
        """Load catalogs from a YAML file.
        
        Args:
            file_path: Path to YAML file
        """
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        self.clear()
        catalogs_data = data.get('catalogs', [])
        
        for catalog_data in catalogs_data:
            catalog = Catalog(**catalog_data)
            self.catalogs.append(catalog)

    def save_to_json(self, file_path: str) -> None:
        """Save catalogs to a JSON file.
        
        Args:
            file_path: Path to save JSON file
        """
        data = {
            'catalogs': [
                {
                    'id': c.id,
                    'information': c.information,
                    'content': c.content,
                    'fetch_all_metadata': c.fetch_all_metadata,
                    'metadata_scan': c.metadata_scan,
                    'target_path': c.target_path
                }
                for c in self.catalogs
            ]
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

    def save_to_yaml(self, file_path: str) -> None:
        """Save catalogs to a YAML file.
        
        Args:
            file_path: Path to save YAML file
        """
        data = {
            'catalogs': [
                {
                    'id': c.id,
                    'information': c.information,
                    'content': c.content,
                    'fetch_all_metadata': c.fetch_all_metadata,
                    'metadata_scan': c.metadata_scan,
                    'target_path': c.target_path
                }
                for c in self.catalogs
            ]
        }
        
        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

    def __len__(self) -> int:
        """Get number of catalogs.
        
        Returns:
            Number of catalogs
        """
        return len(self.catalogs)

    def __iter__(self):
        """Iterate over catalogs.
        
        Yields:
            Catalog objects
        """
        return iter(self.catalogs)

