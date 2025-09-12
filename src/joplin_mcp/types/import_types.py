"""Data models for import functionality."""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


class ImportValidationError(Exception):
    """Raised when import validation fails."""

    pass


class ImportProcessingError(Exception):
    """Raised when import processing fails."""

    pass


@dataclass
class ImportedNote:
    """Represents a note to be imported into Joplin.

    This class holds all the data needed to create a note in Joplin,
    including metadata, content, and organizational information.
    """

    title: str
    body: str
    notebook: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    is_todo: bool = False
    todo_completed: bool = False
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    attachments: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Post-initialization validation."""
        if not self.title.strip():
            # Generate title from body if empty
            if self.body:
                lines = self.body.strip().split("\n")
                self.title = lines[0][:100] if lines else "Untitled Note"
            else:
                self.title = "Untitled Note"

        # Set default timestamps ONLY if not provided
        # This prevents overriding timestamps that were explicitly set
        if self.created_time is None:
            self.created_time = datetime.now()
        if self.updated_time is None:
            # Use created_time if available, otherwise current time
            self.updated_time = self.created_time if self.created_time else datetime.now()


@dataclass
class ImportResult:
    """Results of an import operation.

    Provides comprehensive information about what was processed,
    what succeeded, what failed, and any issues encountered.
    """

    total_processed: int = 0
    successful_imports: int = 0
    failed_imports: int = 0
    skipped_items: int = 0
    created_notebooks: List[str] = field(default_factory=list)
    created_tags: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    skipped_items_list: List[str] = field(default_factory=list)
    processing_time: float = 0.0
    start_time: float = field(default_factory=time.time)

    def add_success(self, note_title: str):
        """Record a successful import."""
        self.successful_imports += 1

    def add_failure(self, note_title: str, error: str):
        """Record a failed import."""
        self.failed_imports += 1
        self.errors.append(f"{note_title}: {error}")

    def add_skip(self, note_title: str, reason: str):
        """Record a skipped item."""
        self.skipped_items += 1
        self.skipped_items_list.append(f"{note_title}: {reason}")

    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)

    def add_created_notebook(self, notebook_name: str):
        """Record a newly created notebook."""
        if notebook_name not in self.created_notebooks:
            self.created_notebooks.append(notebook_name)

    def add_created_tag(self, tag_name: str):
        """Record a newly created tag."""
        if tag_name not in self.created_tags:
            self.created_tags.append(tag_name)

    def finalize(self):
        """Finalize the import result by calculating processing time."""
        self.processing_time = time.time() - self.start_time

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_processed == 0:
            return 0.0
        return (self.successful_imports / self.total_processed) * 100

    @property
    def is_complete_success(self) -> bool:
        """Check if all items were imported successfully."""
        return self.failed_imports == 0 and self.total_processed > 0

    @property
    def is_partial_success(self) -> bool:
        """Check if some items were imported successfully."""
        return self.successful_imports > 0 and self.failed_imports > 0


@dataclass
class ImportOptions:
    """Configuration options for import operations."""

    target_notebook: Optional[str] = None
    create_missing_notebooks: bool = True
    create_missing_tags: bool = True
    preserve_timestamps: bool = True
    handle_duplicates: str = "skip"  # skip|overwrite|rename
    max_batch_size: int = 100
    attachment_handling: str = "embed"  # link|embed|skip
    encoding: str = "utf-8"
    max_file_size_mb: Optional[int] = None
    file_pattern: Optional[str] = None
    preserve_structure: bool = True
    preserve_directory_structure: bool = True
    import_options: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate options after initialization."""
        valid_duplicate_strategies = ["skip", "overwrite", "rename"]
        if self.handle_duplicates not in valid_duplicate_strategies:
            raise ValueError(
                f"handle_duplicates must be one of {valid_duplicate_strategies}"
            )

        valid_attachment_strategies = ["link", "embed", "skip"]
        if self.attachment_handling not in valid_attachment_strategies:
            raise ValueError(
                f"attachment_handling must be one of {valid_attachment_strategies}"
            )

        if self.max_batch_size < 1:
            raise ValueError("max_batch_size must be at least 1")
