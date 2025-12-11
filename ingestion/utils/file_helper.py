import json
import os
import re
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class FileHelper:
    """Helper class for extracting text content from various document formats."""

    @staticmethod
    def get_file_extension(file_path: str) -> str:
        """Return the lowercase file extension for a given file path."""
        return Path(file_path).suffix.lower()

    @staticmethod
    def get_file_size(file_path: str) -> int:
        """
        Get the size of a file in bytes.
        Args:
            file_path (str): Path to the file.
        Returns:
            int: File size in bytes.
        """
        return os.path.getsize(file_path)

    @staticmethod
    def remove_non_text_content(text: str) -> str:
        """
        Remove non-text content like images, notes, slide numbers, navigation elements, etc.
        Args:
            text (str): Raw extracted text content
        Returns:
            str: Cleaned text content with non-text elements removed
        """
        if not text:
            return text

        # First, remove markdown image syntax and HTML comments
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # Remove ![](image.jpg) syntax
        text = re.sub(r"<!-- Slide number: \d+ -->", "", text)  # Remove slide number comments
        text = re.sub(r"### Notes:", "", text)  # Remove notes headers

        # Remove whitespace sequences and newline sequences
        # Replace multiple whitespace characters (including newlines) with single spaces
        cleaned_text = re.sub(r"\s+", " ", text)

        # Remove leading and trailing whitespace
        cleaned_text = cleaned_text.strip()

        return cleaned_text

    @staticmethod
    def get_json_from_file(file_path: str) -> dict | list:
        """
        Get the json from a file.
        Args:
            file_path (str): Path to the file.
        Returns:
            dict: Json content.
        """
        try:
            if not os.path.exists(file_path):
                return None
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return None
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in file {file_path}: {e}")
                    return None
        except Exception as e:
            logger.error(f"Failed to read JSON file {file_path}: {e}")
            return None

    @staticmethod
    def create_json_file(file_path: str, result: Dict[str, Any]) -> str:
        """
        Create a file path.
        Args:
            file_path (str): Path to the file.
        Returns:
            str: File path.
        """
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return file_path

    @staticmethod
    def file_exists(file_path: str) -> bool:
        """
        Check if a file exists.
        Args:
            file_path (str): Path to the file.
        """
        return os.path.exists(file_path)

    @staticmethod
    def delete_file(file_path: str):
        """
        Delete a file.
        Args:
            file_path (str): Path to the file.
        """
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
