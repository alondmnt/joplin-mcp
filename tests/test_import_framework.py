"""Tests for the import framework core components."""

from datetime import datetime
from unittest.mock import Mock

import pytest

from joplin_mcp.imports import JoplinImportEngine
from joplin_mcp.imports.importers.base import BaseImporter, ImportValidationError
from joplin_mcp.imports import ImportedNote, ImportOptions, ImportResult


class TestImportedNote:
    """Test the ImportedNote data model."""

    def test_basic_creation(self):
        """Test basic ImportedNote creation."""
        note = ImportedNote(title="Test Note", body="This is a test note.")

        assert note.title == "Test Note"
        assert note.body == "This is a test note."
        assert note.notebook is None
        assert note.tags == []
        assert note.is_todo is False
        assert note.todo_completed is False
        assert note.attachments == []
        assert note.metadata == {}
        assert isinstance(note.created_time, datetime)
        assert isinstance(note.updated_time, datetime)

    def test_title_from_body_when_empty(self):
        """Test title generation from body when title is empty."""
        note = ImportedNote(title="", body="This should become the title\nSecond line")

        assert note.title == "This should become the title"

    def test_fallback_title_when_no_content(self):
        """Test fallback title when no content available."""
        note = ImportedNote(title="", body="")
        assert note.title == "Untitled Note"

    def test_full_note_creation(self):
        """Test creating a note with all fields."""
        created = datetime(2023, 1, 1, 12, 0, 0)
        updated = datetime(2023, 1, 2, 13, 0, 0)

        note = ImportedNote(
            title="Full Note",
            body="Complete note content",
            notebook="Test Notebook",
            tags=["tag1", "tag2"],
            is_todo=True,
            todo_completed=True,
            created_time=created,
            updated_time=updated,
            attachments=["file1.pdf"],
            metadata={"source": "test"},
        )

        assert note.title == "Full Note"
        assert note.body == "Complete note content"
        assert note.notebook == "Test Notebook"
        assert note.tags == ["tag1", "tag2"]
        assert note.is_todo is True
        assert note.todo_completed is True
        assert note.created_time == created
        assert note.updated_time == updated
        assert note.attachments == ["file1.pdf"]
        assert note.metadata == {"source": "test"}


class TestImportResult:
    """Test the ImportResult data model."""

    def test_basic_creation(self):
        """Test basic ImportResult creation."""
        result = ImportResult()

        assert result.total_processed == 0
        assert result.successful_imports == 0
        assert result.failed_imports == 0
        assert result.skipped_items == 0
        assert result.created_notebooks == []
        assert result.created_tags == []
        assert result.errors == []
        assert result.warnings == []
        assert result.skipped_items_list == []
        assert result.processing_time == 0.0

    def test_add_success(self):
        """Test adding successful imports."""
        result = ImportResult()
        result.add_success("Note 1")
        result.add_success("Note 2")

        assert result.successful_imports == 2

    def test_add_failure(self):
        """Test adding failed imports."""
        result = ImportResult()
        result.add_failure("Note 1", "Error message")

        assert result.failed_imports == 1
        assert len(result.errors) == 1
        assert "Note 1: Error message" in result.errors

    def test_add_skip(self):
        """Test adding skipped items."""
        result = ImportResult()
        result.add_skip("Note 1", "Already exists")

        assert result.skipped_items == 1
        assert len(result.skipped_items_list) == 1
        assert "Note 1: Already exists" in result.skipped_items_list

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        result = ImportResult()
        result.total_processed = 10
        result.successful_imports = 8
        result.failed_imports = 2

        assert result.success_rate == 80.0

    def test_success_rate_no_processing(self):
        """Test success rate when no items processed."""
        result = ImportResult()
        assert result.success_rate == 0.0

    def test_is_complete_success(self):
        """Test complete success detection."""
        result = ImportResult()
        result.total_processed = 5
        result.successful_imports = 5
        result.failed_imports = 0

        assert result.is_complete_success is True

    def test_is_partial_success(self):
        """Test partial success detection."""
        result = ImportResult()
        result.successful_imports = 3
        result.failed_imports = 2

        assert result.is_partial_success is True


class TestImportOptions:
    """Test the ImportOptions data model."""

    def test_default_options(self):
        """Test default option values."""
        options = ImportOptions()

        assert options.target_notebook is None
        assert options.create_missing_notebooks is True
        assert options.create_missing_tags is True
        assert options.preserve_timestamps is True
        assert options.handle_duplicates == "skip"
        assert options.max_batch_size == 100
        assert options.attachment_handling == "embed"
        assert options.encoding == "utf-8"
        assert options.file_pattern is None
        assert options.preserve_structure is True
        assert options.import_options == {}

    def test_invalid_duplicate_strategy(self):
        """Test validation of duplicate handling strategy."""
        with pytest.raises(ValueError, match="handle_duplicates must be one of"):
            ImportOptions(handle_duplicates="invalid")

    def test_invalid_attachment_strategy(self):
        """Test validation of attachment handling strategy."""
        with pytest.raises(ValueError, match="attachment_handling must be one of"):
            ImportOptions(attachment_handling="invalid")

    def test_invalid_batch_size(self):
        """Test validation of batch size."""
        with pytest.raises(ValueError, match="max_batch_size must be at least 1"):
            ImportOptions(max_batch_size=0)


class MockImporter(BaseImporter):
    """Mock importer for testing BaseImporter functionality."""

    async def parse(self, source: str):
        return [ImportedNote(title="Mock Note", body="Mock content")]

    async def validate(self, source: str) -> bool:
        return source.endswith(".mock")

    def get_supported_extensions(self):
        return ["mock"]


class TestBaseImporter:
    """Test the BaseImporter abstract base class."""

    def test_creation_with_options(self):
        """Test importer creation with options."""
        options = ImportOptions(target_notebook="Test")
        importer = MockImporter(options)

        assert importer.options.target_notebook == "Test"

    def test_creation_without_options(self):
        """Test importer creation without options."""
        importer = MockImporter()

        assert isinstance(importer.options, ImportOptions)
        assert importer.options.target_notebook is None

    def test_get_display_name(self):
        """Test display name generation."""
        importer = MockImporter()
        assert importer.get_display_name() == "Mock"

    def test_supports_file(self):
        """Test file support checking."""
        importer = MockImporter()

        # Create a mock Path object
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mock", delete=False) as f:
            temp_file = f.name

        try:
            assert importer.supports_file(temp_file) is True
            assert importer.supports_file("nonexistent.mock") is False
            assert importer.supports_file(temp_file.replace(".mock", ".txt")) is False
        finally:
            os.unlink(temp_file)

    def test_validate_source_exists(self):
        """Test source existence validation."""
        importer = MockImporter()

        with pytest.raises(ImportValidationError, match="Source path does not exist"):
            importer.validate_source_exists("nonexistent_file.txt")


class TestJoplinImportEngine:
    """Test the JoplinImportEngine."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Joplin client."""
        client = Mock()
        client.add_note.return_value = "note123"
        client.add_notebook.return_value = "notebook123"
        client.add_tag.return_value = "tag123"
        client.get_all_notebooks.return_value = []
        client.get_all_tags.return_value = []
        client.search_all.return_value = []
        return client

    @pytest.fixture
    def mock_config(self):
        """Create a mock config."""
        config = Mock()
        config.import_settings = {
            "max_batch_size": 10,
            "create_missing_notebooks": True,
            "create_missing_tags": True,
        }
        return config

    def test_engine_creation(self, mock_client, mock_config):
        """Test import engine creation."""
        engine = JoplinImportEngine(mock_client, mock_config)

        assert engine.client == mock_client
        assert engine.config == mock_config
        assert engine._notebook_cache == {}
        assert engine._tag_cache == {}

    @pytest.mark.asyncio
    async def test_import_empty_batch(self, mock_client, mock_config):
        """Test importing empty batch."""
        engine = JoplinImportEngine(mock_client, mock_config)
        options = ImportOptions()

        result = await engine.import_batch([], options)

        assert result.total_processed == 0
        assert result.successful_imports == 0
        assert result.failed_imports == 0

    @pytest.mark.asyncio
    async def test_import_single_note(self, mock_client, mock_config):
        """Test importing a single note."""
        engine = JoplinImportEngine(mock_client, mock_config)
        options = ImportOptions()

        notes = [ImportedNote(title="Test Note", body="Test content")]
        result = await engine.import_batch(notes, options)

        assert result.total_processed == 1
        assert result.successful_imports == 1
        assert result.failed_imports == 0

        # Verify client was called
        mock_client.add_note.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_notebook_creation(self, mock_client, mock_config):
        """Test notebook creation when it doesn't exist."""
        engine = JoplinImportEngine(mock_client, mock_config)
        options = ImportOptions(create_missing_notebooks=True)
        result = ImportResult()

        notebook_id = await engine.ensure_notebook_exists(
            "New Notebook", options, result
        )

        assert notebook_id == "notebook123"
        assert "New Notebook" in result.created_notebooks
        mock_client.add_notebook.assert_called_once_with(title="New Notebook")

    @pytest.mark.asyncio
    async def test_ensure_tag_creation(self, mock_client, mock_config):
        """Test tag creation when it doesn't exist."""
        engine = JoplinImportEngine(mock_client, mock_config)
        options = ImportOptions(create_missing_tags=True)
        result = ImportResult()

        tag_ids = await engine.ensure_tags_exist(["New Tag"], options, result)

        assert tag_ids == ["tag123"]
        assert "New Tag" in result.created_tags
        mock_client.add_tag.assert_called_once_with(title="New Tag")
