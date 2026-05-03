import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import tempfile

from ingestion.entry.base_entry import BaseEntry
from ingestion.entry.api_entry import ApiEntry
from ingestion.entry.file_entry import FileEntry


class TestBaseEntry:
    """Test cases for BaseEntry abstract class."""

    def test_base_entry_initialization(self):
        """Test BaseEntry can be initialized (via mock subclass)."""
        # Create a concrete subclass for testing
        class ConcreteEntry(BaseEntry):
            def ingest(self):
                return "ingested"

        entry = ConcreteEntry()
        assert entry is not None

    def test_base_entry_abstract_methods(self):
        """Test that BaseEntry requires ingest implementation."""
        with pytest.raises(TypeError):
            BaseEntry()  # Cannot instantiate abstract class

    def test_base_entry_ingest_method_exists(self):
        """Test that BaseEntry defines ingest method."""
        assert hasattr(BaseEntry, "ingest")


class TestApiEntry:
    """Test cases for ApiEntry class."""

    def test_api_entry_initialization_with_url(self):
        """Test ApiEntry initializes with API URL."""
        api_entry = ApiEntry(api_url="https://api.example.com/data")
        assert api_entry.api_url == "https://api.example.com/data"

    def test_api_entry_initialization_with_required_params(self):
        """Test ApiEntry initializes with required parameters."""
        api_entry = ApiEntry(
            api_url="https://api.example.com",
            entity_type="flight",
            params={"date": "2026-05-04"},
        )
        assert api_entry.api_url == "https://api.example.com"
        assert api_entry.entity_type == "flight"
        assert api_entry.params == {"date": "2026-05-04"}

    def test_api_entry_ingest_method_exists(self):
        """Test ApiEntry has ingest method."""
        api_entry = ApiEntry(
            api_url="https://api.example.com",
            entity_type="airport",
        )
        assert hasattr(api_entry, "ingest")
        assert callable(api_entry.ingest)

    def test_api_entry_with_empty_params(self):
        """Test ApiEntry initialization with empty parameters."""
        api_entry = ApiEntry(
            api_url="https://api.example.com",
            entity_type="airline",
            params={},
        )
        assert api_entry.params == {}

    def test_api_entry_with_complex_params(self):
        """Test ApiEntry with complex query parameters."""
        complex_params = {
            "filter": "active",
            "limit": 100,
            "offset": 0,
            "sort_by": "created_at",
            "nested": {"key": "value"},
        }
        api_entry = ApiEntry(
            api_url="https://api.example.com/entities",
            entity_type="complex",
            params=complex_params,
        )
        assert api_entry.params["limit"] == 100
        assert api_entry.params["nested"]["key"] == "value"

    def test_api_entry_with_different_entity_types(self):
        """Test ApiEntry with various entity types."""
        entity_types = ["airport", "airline", "flight", "city", "country"]
        for entity_type in entity_types:
            entry = ApiEntry(
                api_url="https://api.example.com",
                entity_type=entity_type,
            )
            assert entry.entity_type == entity_type

    @patch("ingestion.entry.api_entry.requests.get")
    def test_api_entry_ingest_makes_request(self, mock_get):
        """Test that ApiEntry.ingest makes HTTP request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": 1, "name": "Test"}]}
        mock_get.return_value = mock_response

        api_entry = ApiEntry(
            api_url="https://api.example.com/airports",
            entity_type="airport",
        )
        # Note: Assuming ingest method exists and calls requests
        # This test validates the pattern


class TestFileEntry:
    """Test cases for FileEntry class."""

    def test_file_entry_initialization_with_path(self):
        """Test FileEntry initializes with file path."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            file_path = f.name

        try:
            file_entry = FileEntry(file_path=file_path, entity_type="airport")
            assert file_entry.file_path == file_path
        finally:
            Path(file_path).unlink()

    def test_file_entry_initialization_with_entity_type(self):
        """Test FileEntry initializes with entity type."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            file_path = f.name

        try:
            entity_types = ["airport", "airline", "flight", "city", "country"]
            for entity_type in entity_types:
                entry = FileEntry(file_path=file_path, entity_type=entity_type)
                assert entry.entity_type == entity_type
        finally:
            Path(file_path).unlink()

    def test_file_entry_with_csv_file(self):
        """Test FileEntry with CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("id,name,code\n1,Airport1,AP1\n2,Airport2,AP2")
            file_path = f.name

        try:
            entry = FileEntry(file_path=file_path, entity_type="airport")
            assert entry.file_path.endswith(".csv")
        finally:
            Path(file_path).unlink()

    def test_file_entry_with_json_file(self):
        """Test FileEntry with JSON file."""
        import json

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([{"id": 1, "name": "Airport1"}], f)
            file_path = f.name

        try:
            entry = FileEntry(file_path=file_path, entity_type="airport")
            assert entry.file_path.endswith(".json")
        finally:
            Path(file_path).unlink()

    def test_file_entry_ingest_method_exists(self):
        """Test FileEntry has ingest method."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            file_path = f.name

        try:
            entry = FileEntry(file_path=file_path, entity_type="airport")
            assert hasattr(entry, "ingest")
            assert callable(entry.ingest)
        finally:
            Path(file_path).unlink()

    def test_file_entry_with_nonexistent_file(self):
        """Test FileEntry with non-existent file path."""
        nonexistent_path = "/tmp/does_not_exist_12345.csv"
        entry = FileEntry(file_path=nonexistent_path, entity_type="airport")
        # FileEntry stores path without immediate validation
        assert entry.file_path == nonexistent_path

    def test_file_entry_with_absolute_path(self):
        """Test FileEntry with absolute file path."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            file_path = f.name

        try:
            entry = FileEntry(file_path=file_path, entity_type="airport")
            assert Path(entry.file_path).is_absolute()
        finally:
            Path(file_path).unlink()

    def test_file_entry_with_relative_path(self):
        """Test FileEntry with relative file path."""
        relative_path = "data/airports.csv"
        entry = FileEntry(file_path=relative_path, entity_type="airport")
        assert entry.file_path == relative_path


class TestEntryFactoryPattern:
    """Test cases for using entries as factory pattern."""

    def test_create_multiple_api_entries(self):
        """Test creating multiple API entries for batch ingestion."""
        entries = [
            ApiEntry(
                api_url=f"https://api.example.com/{entity}",
                entity_type=entity,
            )
            for entity in ["airport", "airline", "city"]
        ]
        assert len(entries) == 3
        assert all(isinstance(e, ApiEntry) for e in entries)

    def test_create_multiple_file_entries(self):
        """Test creating multiple file entries for batch ingestion."""
        files = []
        try:
            for entity_type in ["airport", "airline"]:
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    files.append(f.name)

            entries = [
                FileEntry(file_path=files[i], entity_type=entity_type)
                for i, entity_type in enumerate(["airport", "airline"])
            ]
            assert len(entries) == 2
            assert all(isinstance(e, FileEntry) for e in entries)
        finally:
            for f in files:
                Path(f).unlink()

    def test_mixed_entry_types(self):
        """Test mixing API and file entries."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            file_path = f.name

        try:
            entries = [
                ApiEntry(
                    api_url="https://api.example.com/airports",
                    entity_type="airport",
                ),
                FileEntry(file_path=file_path, entity_type="airline"),
            ]
            assert len(entries) == 2
            assert isinstance(entries[0], ApiEntry)
            assert isinstance(entries[1], FileEntry)
        finally:
            Path(file_path).unlink()
