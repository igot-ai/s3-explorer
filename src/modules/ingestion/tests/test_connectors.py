"""Unit tests for ingestion core connectors."""

import io

from unittest.mock import Mock

from ingestion.core.connectors.s3_connector import S3SourceConnector


class TestS3SourceConnector:
    def test_list_folders_top_level(self):
        provider = Mock()
        provider.list_files.return_value = [
            {"name": "root/folder1/a.pdf", "size": 1},
            {"name": "root/folder1/b.pdf", "size": 1},
            {"name": "root/folder2/c.pdf", "size": 1},
            {"name": "root/file-at-root.pdf", "size": 1},
        ]

        connector = S3SourceConnector(provider)
        folders = connector.list_folders("root/")

        assert folders == ["root/folder1/", "root/folder2/"]

    def test_walk_folder_non_recursive_skips_dirs_and_zero_size(self):
        provider = Mock()
        provider.list_files.return_value = [
            {"name": "root/folder/", "type": "directory"},
            {"name": "root/folder/empty.pdf", "size": 0},
            {"name": "root/folder/a.pdf", "size": 10},
            {"name": "root/folder/b.docx", "size": 20},
        ]

        connector = S3SourceConnector(provider)
        files = list(connector.walk_folder("root/folder/", recursive=False))

        assert [f.source_path for f in files] == ["root/folder/a.pdf", "root/folder/b.docx"]
        assert [f.file_type for f in files] == ["pdf", "docx"]

    def test_walk_folder_recursive_descends_subfolders(self):
        provider = Mock()

        def list_files_side_effect(prefix):
            if prefix == "root/folder/":
                return [
                    {"name": "root/folder/sub/", "type": "directory"},
                    {"name": "root/folder/a.pdf", "size": 10},
                ]
            if prefix == "root/folder/sub/":
                return [{"name": "root/folder/sub/b.pdf", "size": 10}]
            return []

        provider.list_files.side_effect = list_files_side_effect

        connector = S3SourceConnector(provider)
        files = list(connector.walk_folder("root/folder/", recursive=True))

        # Order is implementation-dependent (connector may yield subfolder files first).
        assert sorted([f.source_path for f in files]) == sorted(
            ["root/folder/a.pdf", "root/folder/sub/b.pdf"]
        )

    def test_download_file_delegates_to_provider(self):
        provider = Mock()
        stream = io.BytesIO(b"abc")
        provider.download_file.return_value = stream

        connector = S3SourceConnector(provider)
        result = connector.download_file("root/folder/a.pdf")

        assert result is stream
        provider.download_file.assert_called_once_with("root/folder/a.pdf")

    def test_file_exists_uses_metadata(self):
        provider = Mock()
        provider.list_files.return_value = [{"name": "root/folder/a.pdf", "size": 10}]

        connector = S3SourceConnector(provider)
        assert connector.file_exists("root/folder/a.pdf") is True
        assert connector.file_exists("root/folder/missing.pdf") is False


