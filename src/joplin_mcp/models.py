"""
Joplin MCP data models.

This module defines Pydantic models for representing Joplin entities in the MCP context,
with proper validation, type conversion, and utility methods.
"""

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator, validator


class NotePriority(Enum):
    """Priority levels for notes."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

    @classmethod
    def from_string(cls, value: str) -> "NotePriority":
        """Create priority from string value."""
        value_lower = value.lower()
        mapping = {
            "low": cls.LOW,
            "normal": cls.NORMAL,
            "high": cls.HIGH,
            "urgent": cls.URGENT,
        }
        return mapping[value_lower]


class JoplinTimestamp:
    """Utility class for handling Joplin timestamp conversions."""

    @staticmethod
    def to_datetime(timestamp: int) -> datetime:
        """Convert Joplin timestamp (Unix milliseconds) to datetime object."""
        return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)

    @staticmethod
    def from_datetime(dt: datetime) -> int:
        """Convert datetime object to Joplin timestamp (Unix milliseconds)."""
        return int(dt.timestamp() * 1000)

    @staticmethod
    def now() -> int:
        """Get current timestamp in Joplin format."""
        return int(datetime.now(timezone.utc).timestamp() * 1000)


class MCPNote(BaseModel):
    """
    Pydantic model for Joplin notes in MCP context.

    Handles validation, type conversion, and provides utility methods
    for working with Joplin note data.
    """

    # Required fields
    id: str = Field(..., description="Unique note identifier")
    title: str = Field(..., description="Note title")
    body: str = Field(..., description="Note content in Markdown")
    created_time: int = Field(..., description="Creation timestamp (Unix milliseconds)")
    updated_time: int = Field(
        ..., description="Last update timestamp (Unix milliseconds)"
    )

    # Optional fields with defaults
    parent_id: Optional[str] = Field(None, description="Parent notebook ID")
    markup_language: int = Field(1, description="Markup language (1=Markdown)")
    is_todo: bool = Field(False, description="Whether this is a todo note")
    todo_completed: bool = Field(False, description="Whether todo is completed")
    is_conflict: bool = Field(False, description="Whether note has sync conflicts")
    latitude: float = Field(0.0, description="Geographic latitude")
    longitude: float = Field(0.0, description="Geographic longitude")
    altitude: float = Field(0.0, description="Geographic altitude")

    # Additional fields for MCP functionality
    tags: List[str] = Field(default_factory=list, description="Associated tags")

    @validator("id")
    def validate_id(cls, v):
        """Validate that ID is a 32-character hexadecimal string."""
        if not isinstance(v, str) or len(v) != 32:
            raise ValueError("ID must be 32 characters long")
        if not re.match(r"^[a-f0-9]{32}$", v):
            raise ValueError("ID must be hexadecimal characters only")
        return v

    @validator("created_time", "updated_time")
    def validate_timestamps(cls, v):
        """Validate timestamps are non-negative integers."""
        if not isinstance(v, int) or v < 0:
            raise ValueError("Timestamps must be non-negative integers")
        return v

    @validator("is_todo", "todo_completed", "is_conflict", pre=True)
    def coerce_bool_fields(cls, v):
        """Convert integer boolean fields to Python booleans."""
        if isinstance(v, int):
            return bool(v)
        return v

    def to_joplin_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format expected by Joplin API."""
        data = self.dict(exclude={"tags"})

        # Convert boolean fields back to integers for Joplin API
        bool_fields = ["is_todo", "todo_completed", "is_conflict"]
        for field in bool_fields:
            if field in data:
                data[field] = int(data[field])

        return data

    def to_mcp_summary(self) -> Dict[str, Any]:
        """Create a summary suitable for MCP responses."""
        # Truncate body to create excerpt
        excerpt = self.body[:200]
        if len(self.body) > 200:
            excerpt = excerpt.rstrip() + "..."

        return {
            "id": self.id,
            "title": self.title,
            "excerpt": excerpt,
            "updated_time": self.updated_time,
            "parent_id": self.parent_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format (alias for to_joplin_dict)."""
        return self.to_joplin_dict()

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "ignore"  # Allow extra fields from Joplin API


class MCPNotebook(BaseModel):
    """
    Pydantic model for Joplin notebooks in MCP context.

    Handles notebook hierarchies and provides utility methods
    for working with parent-child relationships.
    """

    # Required fields
    id: str = Field(..., description="Unique notebook identifier")
    title: str = Field(..., description="Notebook title")
    created_time: int = Field(..., description="Creation timestamp (Unix milliseconds)")
    updated_time: int = Field(
        ..., description="Last update timestamp (Unix milliseconds)"
    )

    # Optional fields
    parent_id: Optional[str] = Field(None, description="Parent notebook ID")
    share_id: Optional[str] = Field(None, description="Share ID for shared notebooks")
    master_key_id: Optional[str] = Field(
        None, description="Master key ID for encryption"
    )

    @validator("id")
    def validate_id(cls, v):
        """Validate that ID is a 32-character hexadecimal string."""
        if not isinstance(v, str) or len(v) != 32:
            raise ValueError("ID must be 32 characters long")
        if not re.match(r"^[a-f0-9]{32}$", v):
            raise ValueError("ID must be hexadecimal characters only")
        return v

    @validator("parent_id")
    def validate_parent_id(cls, v):
        """Validate that parent_id follows the same format as id when provided."""
        if v is None or v == "":
            return None  # Convert empty strings to None
        if not isinstance(v, str) or len(v) != 32:
            raise ValueError("Parent ID must be 32 characters long")
        if not re.match(r"^[a-f0-9]{32}$", v):
            raise ValueError("Parent ID must be hexadecimal characters only")
        return v

    @validator("created_time", "updated_time")
    def validate_timestamps(cls, v):
        """Validate timestamps are non-negative integers."""
        if not isinstance(v, int) or v < 0:
            raise ValueError("Timestamps must be non-negative integers")
        return v

    def is_root_notebook(self) -> bool:
        """Check if this is a root notebook (no parent)."""
        return self.parent_id is None

    def is_child_of(self, parent_notebook_id: str) -> bool:
        """Check if this notebook is a direct child of the given parent."""
        return self.parent_id == parent_notebook_id

    def to_joplin_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format expected by Joplin API."""
        return self.dict()

    def to_mcp_summary(self) -> Dict[str, Any]:
        """Create a summary suitable for MCP responses."""
        return {
            "id": self.id,
            "title": self.title,
            "parent_id": self.parent_id,
            "created_time": self.created_time,
            "updated_time": self.updated_time,
            "is_root": self.is_root_notebook(),
        }

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "ignore"  # Allow extra fields from Joplin API


class MCPTag(BaseModel):
    """
    Pydantic model for Joplin tags in MCP context.

    Handles tag validation and provides utility methods
    for working with tag data.
    """

    # Required fields
    id: str = Field(..., description="Unique tag identifier")
    title: str = Field(..., description="Tag name")
    created_time: int = Field(..., description="Creation timestamp (Unix milliseconds)")
    updated_time: int = Field(
        ..., description="Last update timestamp (Unix milliseconds)"
    )

    @validator("id")
    def validate_id(cls, v):
        """Validate that ID is a 32-character hexadecimal string."""
        if not isinstance(v, str) or len(v) != 32:
            raise ValueError("ID must be 32 characters long")
        if not re.match(r"^[a-f0-9]{32}$", v):
            raise ValueError("ID must be hexadecimal characters only")
        return v

    @validator("created_time", "updated_time")
    def validate_timestamps(cls, v):
        """Validate timestamps are non-negative integers."""
        if not isinstance(v, int) or v < 0:
            raise ValueError("Timestamps must be non-negative integers")
        return v

    @validator("title")
    def normalize_title(cls, v):
        """Normalize tag title (lowercase and trim whitespace)."""
        if isinstance(v, str):
            return v.strip().lower()
        return v

    def to_joplin_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format expected by Joplin API."""
        return self.dict()

    def to_mcp_summary(self) -> Dict[str, Any]:
        """Create a summary suitable for MCP responses."""
        return {
            "id": self.id,
            "title": self.title,
            "created_time": self.created_time,
            "updated_time": self.updated_time,
        }

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "ignore"  # Allow extra fields from Joplin API


class MCPSearchResult(BaseModel):
    """
    Pydantic model for search results in MCP context.

    Provides comprehensive search result handling with pagination,
    filtering, and utility methods for MCP responses.
    """

    items: List[Dict[str, Any]] = Field(
        default_factory=list, description="Search result items"
    )
    has_more: bool = Field(False, description="Whether more results are available")
    total_count: Optional[int] = Field(None, description="Total number of results")
    page: Optional[int] = Field(None, description="Current page number")

    # Enhanced search fields
    search_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Enhanced search metadata"
    )
    pagination: Optional[Dict[str, Any]] = Field(
        None, description="Detailed pagination information"
    )
    facets: Optional[Dict[str, List[Dict[str, Any]]]] = Field(
        None, description="Faceted search results"
    )
    suggestions: Optional[List[Dict[str, Any]]] = Field(
        None, description="Related content suggestions"
    )
    aggregations: Optional[Dict[str, Any]] = Field(
        None, description="Search result aggregations"
    )

    def get_pagination_info(self) -> Dict[str, Any]:
        """Get pagination information."""
        return {
            "has_more": self.has_more,
            "total_count": self.total_count,
            "page": self.page,
            "items_count": len(self.items),
        }

    def add_item(self, item: Dict[str, Any]) -> None:
        """Add an item to the search results."""
        self.items.append(item)

    def filter_by_type(self, item_type: str) -> List[Dict[str, Any]]:
        """Filter search results by type."""
        return [item for item in self.items if item.get("type") == item_type]

    def to_mcp_response(self) -> Dict[str, Any]:
        """Convert to MCP response format."""
        response = {
            "content": {"items": self.items},
            "isError": False,
            "meta": {
                "has_more": self.has_more,
                "total_count": self.total_count,
                "page": self.page,
                "items_count": len(self.items),
            },
        }

        # Add enhanced fields if present
        if self.search_metadata:
            response["meta"]["search_metadata"] = self.search_metadata
        if self.pagination:
            response["meta"]["pagination"] = self.pagination
        if self.facets:
            response["meta"]["facets"] = self.facets
        if self.suggestions:
            response["meta"]["suggestions"] = self.suggestions
        if self.aggregations:
            response["meta"]["aggregations"] = self.aggregations

        return response

    def merge(self, other: "MCPSearchResult") -> "MCPSearchResult":
        """Merge this search result with another."""
        merged_items = self.items + other.items
        merged_total = (self.total_count or 0) + (other.total_count or 0)

        return MCPSearchResult(
            items=merged_items,
            has_more=self.has_more or other.has_more,
            total_count=merged_total,
            page=self.page,  # Keep current page
        )

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "ignore"  # Allow extra fields


class MCPPaginatedResponse(BaseModel):
    """
    Pydantic model for paginated API responses in MCP context.

    Provides comprehensive pagination handling with navigation URLs,
    validation, and utility methods for MCP responses.
    """

    items: List[Dict[str, Any]] = Field(
        default_factory=list, description="Paginated items"
    )
    page: int = Field(..., description="Current page number (1-based)")
    per_page: int = Field(..., description="Number of items per page")
    total_count: int = Field(..., description="Total number of items across all pages")
    total_pages: int = Field(..., description="Total number of pages")
    base_url: Optional[str] = Field(None, description="Base URL for navigation links")
    endpoint: Optional[str] = Field(
        None, description="API endpoint for navigation links"
    )

    @validator("page")
    def validate_page(cls, v):
        """Validate that page is positive."""
        if v < 1:
            raise ValueError("Page must be >= 1")
        return v

    @validator("per_page")
    def validate_per_page(cls, v):
        """Validate that per_page is positive."""
        if v < 1:
            raise ValueError("Per page must be >= 1")
        return v

    @validator("total_count")
    def validate_total_count(cls, v):
        """Validate that total_count is non-negative."""
        if v < 0:
            raise ValueError("Total count must be >= 0")
        return v

    def has_next_page(self) -> bool:
        """Check if there's a next page."""
        return self.page < self.total_pages

    def has_previous_page(self) -> bool:
        """Check if there's a previous page."""
        return self.page > 1

    def is_last_page(self) -> bool:
        """Check if this is the last page."""
        return self.page == self.total_pages

    def is_empty(self) -> bool:
        """Check if the response has no items."""
        return len(self.items) == 0

    def get_navigation_urls(self) -> Dict[str, Optional[str]]:
        """Generate navigation URLs for pagination."""
        if not self.base_url or not self.endpoint:
            return {"next": None, "previous": None, "first": None, "last": None}

        base = f"{self.base_url}{self.endpoint}"

        def make_url(page_num: int) -> str:
            return f"{base}?page={page_num}&per_page={self.per_page}"

        return {
            "next": make_url(self.page + 1) if self.has_next_page() else None,
            "previous": make_url(self.page - 1) if self.has_previous_page() else None,
            "first": make_url(1) if self.total_pages > 0 else None,
            "last": make_url(self.total_pages) if self.total_pages > 0 else None,
        }

    def to_mcp_response(self) -> Dict[str, Any]:
        """Convert to MCP response format."""
        return {
            "content": {"items": self.items},
            "isError": False,
            "meta": {
                "pagination": {
                    "page": self.page,
                    "per_page": self.per_page,
                    "total_count": self.total_count,
                    "total_pages": self.total_pages,
                    "has_next": self.has_next_page(),
                    "has_previous": self.has_previous_page(),
                }
            },
        }

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "ignore"


class MCPErrorResponse(BaseModel):
    """
    Pydantic model for API error responses in MCP context.

    Provides comprehensive error handling with status codes,
    validation errors, and utility methods for error categorization.
    """

    error_code: str = Field(..., description="Unique error code")
    message: str = Field(..., description="Human-readable error message")
    status_code: int = Field(..., description="HTTP status code")
    details: Optional[Dict[str, Any]] = Field(
        None, description="Additional error details"
    )
    validation_errors: Optional[List[Dict[str, str]]] = Field(
        None, description="Field validation errors"
    )
    timestamp: Optional[int] = Field(
        None, description="Error timestamp (Unix milliseconds)"
    )

    def is_client_error(self) -> bool:
        """Check if this is a client error (4xx status code)."""
        return 400 <= self.status_code < 500

    def is_server_error(self) -> bool:
        """Check if this is a server error (5xx status code)."""
        return 500 <= self.status_code < 600

    def has_validation_errors(self) -> bool:
        """Check if this error has validation errors."""
        return self.validation_errors is not None and len(self.validation_errors) > 0

    def get_field_errors(self, field_name: str) -> List[str]:
        """Get validation errors for a specific field."""
        if not self.validation_errors:
            return []

        return [
            error["message"]
            for error in self.validation_errors
            if error.get("field") == field_name
        ]

    @classmethod
    def from_exception(
        cls, exception: Exception, error_code: str, status_code: int = 500
    ) -> "MCPErrorResponse":
        """Create an error response from a Python exception."""
        return cls(
            error_code=error_code,
            message=str(exception),
            status_code=status_code,
            timestamp=JoplinTimestamp.now(),
        )

    def to_mcp_response(self) -> Dict[str, Any]:
        """Convert to MCP error response format."""
        response = {
            "isError": True,
            "error": {
                "code": self.error_code,
                "message": self.message,
                "status_code": self.status_code,
            },
        }

        if self.details:
            response["error"]["details"] = self.details

        if self.validation_errors:
            response["error"]["validation_errors"] = self.validation_errors

        return response

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "ignore"


class MCPAPIResponse(BaseModel):
    """
    Pydantic model for generic API responses in MCP context.

    Provides a unified wrapper for both successful and error responses
    with metadata support and factory methods.
    """

    success: bool = Field(..., description="Whether the operation was successful")
    data: Optional[Dict[str, Any]] = Field(
        None, description="Response data for successful operations"
    )
    error_info: Optional[MCPErrorResponse] = Field(
        None, description="Error information for failed operations"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional response metadata"
    )
    timestamp: int = Field(
        default_factory=JoplinTimestamp.now, description="Response timestamp"
    )

    @model_validator(mode="after")
    def validate_response_state(self):
        """Validate that response has either data or error, but not both."""
        if self.success and self.error_info is not None:
            raise ValueError("Successful response cannot have error")

        if not self.success and self.data is not None:
            raise ValueError("Failed response cannot have data")

        if not self.success and self.error_info is None:
            raise ValueError("Failed response must have error")

        # Allow successful responses with no data (e.g., DELETE operations)
        return self

    def is_success(self) -> bool:
        """Check if the response indicates success."""
        return self.success

    def is_error(self) -> bool:
        """Check if the response indicates an error."""
        return not self.success

    @property
    def error(self) -> Optional[MCPErrorResponse]:
        """Property to access error information (alias for error_info)."""
        return self.error_info

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a metadata value by key."""
        if not self.metadata:
            return default
        return self.metadata.get(key, default)

    @classmethod
    def create_success(
        cls,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "MCPAPIResponse":
        """Create a successful API response."""
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def create_error(
        cls,
        error_code: str,
        message: str,
        status_code: int,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "MCPAPIResponse":
        """Create an error API response."""
        error = MCPErrorResponse(
            error_code=error_code,
            message=message,
            status_code=status_code,
            details=details,
        )

        return cls(success=False, error_info=error, metadata=metadata)

    @classmethod
    def success_response(
        cls,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "MCPAPIResponse":
        """Create a successful API response (alias for create_success)."""
        return cls.create_success(data, metadata)

    @classmethod
    def error_response(
        cls,
        error_code: str,
        message: str,
        status_code: int,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "MCPAPIResponse":
        """Create an error API response (alias for create_error)."""
        return cls.create_error(error_code, message, status_code, details, metadata)

    def to_mcp_response(self) -> Dict[str, Any]:
        """Convert to MCP response format."""
        if self.success:
            response = {"isError": False, "content": self.data or {}}
        else:
            response = self.error_info.to_mcp_response()

        if self.metadata:
            response["meta"] = self.metadata

        return response

    class Config:
        """Pydantic configuration."""

        validate_assignment = True
        extra = "ignore"
