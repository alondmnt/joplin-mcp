"""Core import engine for processing batches of imported notes."""

import asyncio
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from joppy.client_api import ClientApi

from .config import JoplinMCPConfig
from .types.import_types import ImportedNote, ImportOptions, ImportResult

logger = logging.getLogger(__name__)


class JoplinImportEngine:
    """Core engine for processing import operations.

    Handles batch processing of ImportedNote objects, including:
    - Creating missing notebooks and tags
    - Managing duplicates
    - Error handling and recovery
    - Progress tracking
    """

    def __init__(self, client: ClientApi, config: JoplinMCPConfig):
        """Initialize the import engine.

        Args:
            client: Configured Joplin API client
            config: MCP configuration instance
        """
        self.client = client
        self.config = config
        self._notebook_cache: Dict[str, str] = {}  # name -> id
        self._tag_cache: Dict[str, str] = {}  # name -> id

    async def import_batch(
        self, notes: List[ImportedNote], options: ImportOptions
    ) -> ImportResult:
        """Process a batch of notes for import.

        Args:
            notes: List of ImportedNote objects to process
            options: Import configuration options

        Returns:
            ImportResult with comprehensive processing information
        """
        result = ImportResult()
        result.total_processed = len(notes)

        try:
            # Pre-populate caches for performance
            await self._populate_caches()

            # Prepare tracking for created notes to support link rewriting
            created_records: List[Dict[str, str]] = []

            # Process notes in batches to avoid overwhelming Joplin
            batch_size = min(options.max_batch_size, 50)

            for i in range(0, len(notes), batch_size):
                batch = notes[i : i + batch_size]
                await self._process_batch(batch, options, result, created_records)

                # Small delay between batches to be gentle on Joplin
                if i + batch_size < len(notes):
                    await asyncio.sleep(0.1)

            # After creating all notes, attempt to rewrite internal note links
            try:
                await self._rewrite_internal_note_links(created_records, result)
            except Exception as e:
                logger.warning(f"Internal link rewrite failed: {e}")

        except Exception as e:
            result.add_failure("Batch Processing", f"Critical error: {str(e)}")
            logger.error(f"Import batch failed: {e}")

        finally:
            result.finalize()

        return result

    async def _process_batch(
        self,
        batch: List[ImportedNote],
        options: ImportOptions,
        result: ImportResult,
        created_records: List[Dict[str, str]],
    ) -> None:
        """Process a single batch of notes.

        Args:
            batch: Batch of notes to process
            options: Import options
            result: Result object to update
        """
        for note in batch:
            try:
                success, message, new_id = await self.create_note_safe(
                    note, options, result
                )
                if success:
                    result.add_success(note.title)
                    # Track created note info for link rewriting
                    try:
                        record: Dict[str, str] = {
                            "new_id": new_id or "",
                            "title": note.title,
                        }
                        # Try to capture original identifiers for mapping
                        # RAW/JEX often include original Joplin id
                        orig_id = None
                        if isinstance(note.metadata, dict):
                            orig_id = note.metadata.get("id") or note.metadata.get(
                                "joplin_id"
                            )
                            source_file = note.metadata.get("source_file")
                            if source_file:
                                record["source_file"] = str(source_file)
                            original_format = note.metadata.get("original_format")
                            if original_format:
                                record["original_format"] = str(original_format)
                        if orig_id and isinstance(orig_id, str):
                            record["original_id"] = orig_id
                        created_records.append(record)
                    except Exception:
                        # Non-fatal tracking failure
                        pass
                else:
                    result.add_failure(note.title, message)

            except Exception as e:
                result.add_failure(note.title, f"Unexpected error: {str(e)}")
                logger.error(f"Failed to process note '{note.title}': {e}")

    async def create_note_safe(
        self, note: ImportedNote, options: ImportOptions, result: ImportResult
    ) -> Tuple[bool, str, Optional[str]]:
        """Safely create a single note with error handling.

        Args:
            note: Note to create
            options: Import options
            result: Result object for tracking created resources

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Handle notebook assignment
            notebook_id = None
            if note.notebook:
                notebook_id = await self.ensure_notebook_exists(
                    note.notebook, options, result
                )
            elif options.target_notebook:
                notebook_id = await self.ensure_notebook_exists(
                    options.target_notebook, options, result
                )

            # Handle duplicate checking
            if options.handle_duplicates != "overwrite":
                existing_id = await self._find_existing_note(note.title, notebook_id)
                if existing_id:
                    if options.handle_duplicates == "skip":
                        result.add_skip(note.title, "Note with same title exists")
                        return True, "Skipped (duplicate)"
                    elif options.handle_duplicates == "rename":
                        note.title = await self._generate_unique_title(
                            note.title, notebook_id
                        )

            # Create the note
            note_id = self.client.add_note(
                title=note.title,
                body=note.body,
                parent_id=notebook_id,
                is_todo=note.is_todo,
                todo_completed=note.todo_completed,
            )

            # add_note returns the note ID directly as a string
            if not note_id or not isinstance(note_id, str):
                return False, "Failed to get note ID from creation response", None

            # Handle tags
            if note.tags:
                await self._apply_tags_to_note(note_id, note.tags, options, result)

            # Handle timestamps if preserve_timestamps is enabled
            if options.preserve_timestamps and (note.created_time or note.updated_time):
                await self._update_note_timestamps(note_id, note)

            return True, f"Created successfully (ID: {note_id})", note_id

        except Exception as e:
            error_msg = str(e)
            if "already exists" in error_msg.lower():
                if options.handle_duplicates == "skip":
                    result.add_skip(note.title, "Duplicate note")
                    return True, "Skipped (duplicate)"

            return False, f"Creation failed: {error_msg}", None

    async def _rewrite_internal_note_links(
        self, created_records: List[Dict[str, str]], result: ImportResult
    ) -> None:
        """Rewrite internal note links of the form [text](:/oldid) to their new IDs.

        Args:
            created_records: List of dicts with keys including 'new_id' and optional 'original_id'.
            result: ImportResult to record warnings.
        """
        if not created_records:
            return

        # Build mapping from original Joplin IDs to new IDs
        id_map: Dict[str, str] = {}
        for rec in created_records:
            orig = rec.get("original_id")
            new = rec.get("new_id")
            if orig and new:
                id_map[orig] = new

        if not id_map:
            # Nothing to rewrite for now (future: path-based mapping)
            return

        # Pattern matches both image and normal md links: ![alt](:/id) or [text](:/id)
        link_re = re.compile(r"(!?\[[^\]]*\])\(:\/([a-f0-9]{32})(#[^)]+)?\)")

        # Iterate through created notes to rewrite bodies
        for rec in created_records:
            note_id = rec.get("new_id")
            if not note_id:
                continue

            try:
                # Fetch the current note content (ensure body is included)
                note_obj = self.client.get_note(note_id, fields="id,title,body")
                body = getattr(note_obj, "body", None)
                if not body or ":/" not in body:
                    continue

                def _sub(match: re.Match) -> str:
                    prefix = match.group(1)
                    old_id = match.group(2)
                    anchor = match.group(3) or ""
                    new_id = id_map.get(old_id)
                    if new_id and new_id != old_id:
                        return f"{prefix}(:/{new_id}{anchor})"
                    return match.group(0)

                new_body = link_re.sub(_sub, body)
                if new_body != body:
                    self.client.modify_note(note_id, body=new_body)
                    result.add_warning(
                        f"Rewrote internal links in note '{rec.get('title', note_id)}'"
                    )
            except Exception as e:
                logger.warning(
                    f"Failed rewriting links for note {note_id}: {e}"
                )

    async def ensure_notebook_exists(
        self, notebook_name: str, options: ImportOptions, result: ImportResult
    ) -> Optional[str]:
        """Ensure a notebook exists, creating it if necessary.

        Args:
            notebook_name: Name of the notebook
            options: Import options
            result: Result object for tracking

        Returns:
            Notebook ID if successful, None otherwise
        """
        if not notebook_name or not notebook_name.strip():
            return None

        # Check cache first
        if notebook_name in self._notebook_cache:
            return self._notebook_cache[notebook_name]

        try:
            # Try to find existing notebook
            notebooks = self.client.get_all_notebooks()
            for notebook in notebooks:
                if notebook.title == notebook_name:
                    notebook_id = notebook.id
                    self._notebook_cache[notebook_name] = notebook_id
                    return notebook_id

            # Create new notebook if allowed
            if options.create_missing_notebooks:
                notebook_id = self.client.add_notebook(title=notebook_name)
                if notebook_id:
                    self._notebook_cache[notebook_name] = notebook_id
                    result.add_created_notebook(notebook_name)
                    return notebook_id

        except Exception as e:
            logger.error(f"Failed to ensure notebook '{notebook_name}': {e}")
            result.add_warning(
                f"Could not create/find notebook '{notebook_name}': {str(e)}"
            )

        return None

    async def ensure_tags_exist(
        self, tag_names: List[str], options: ImportOptions, result: ImportResult
    ) -> List[str]:
        """Ensure tags exist, creating them if necessary.

        Args:
            tag_names: List of tag names
            options: Import options
            result: Result object for tracking

        Returns:
            List of tag IDs
        """
        tag_ids = []

        for tag_name in tag_names:
            if not tag_name or not tag_name.strip():
                continue

            # Check cache first
            if tag_name in self._tag_cache:
                tag_ids.append(self._tag_cache[tag_name])
                continue

            try:
                # Try to find existing tag
                tags = self.client.get_all_tags()
                found = False
                for tag in tags:
                    if tag.title == tag_name:
                        tag_id = tag.id
                        self._tag_cache[tag_name] = tag_id
                        tag_ids.append(tag_id)
                        found = True
                        break

                # Create new tag if allowed and not found
                if not found and options.create_missing_tags:
                    tag_id = self.client.add_tag(title=tag_name)
                    if tag_id:
                        self._tag_cache[tag_name] = tag_id
                        tag_ids.append(tag_id)
                        result.add_created_tag(tag_name)

            except Exception as e:
                logger.error(f"Failed to ensure tag '{tag_name}': {e}")
                result.add_warning(f"Could not create/find tag '{tag_name}': {str(e)}")

        return tag_ids

    async def _apply_tags_to_note(
        self,
        note_id: str,
        tag_names: List[str],
        options: ImportOptions,
        result: ImportResult,
    ) -> None:
        """Apply tags to a note.

        Args:
            note_id: ID of the note
            tag_names: List of tag names to apply
            options: Import options
            result: Result object for tracking
        """
        try:
            tag_ids = await self.ensure_tags_exist(tag_names, options, result)

            for tag_id in tag_ids:
                try:
                    self.client.add_tag_to_note(tag_id=tag_id, note_id=note_id)
                except Exception as e:
                    # Non-fatal error, just log it
                    logger.warning(
                        f"Failed to apply tag {tag_id} to note {note_id}: {e}"
                    )

        except Exception as e:
            result.add_warning(f"Failed to apply tags to note: {str(e)}")

    async def _populate_caches(self) -> None:
        """Pre-populate notebook and tag caches for performance."""
        try:
            # Cache notebooks
            notebooks = self.client.get_all_notebooks()
            for notebook in notebooks:
                name = notebook.title
                notebook_id = notebook.id
                if name and notebook_id:
                    self._notebook_cache[name] = notebook_id

            # Cache tags
            tags = self.client.get_all_tags()
            for tag in tags:
                name = tag.title
                tag_id = tag.id
                if name and tag_id:
                    self._tag_cache[name] = tag_id

        except Exception as e:
            logger.warning(f"Failed to populate caches: {e}")

    async def _find_existing_note(
        self, title: str, notebook_id: Optional[str]
    ) -> Optional[str]:
        """Find existing note with same title in the same notebook.

        Args:
            title: Note title to search for
            notebook_id: Notebook ID to search in (None for all notebooks)

        Returns:
            Note ID if found, None otherwise
        """
        try:
            # Search for notes with exact title match
            search_query = f'title:"{title}"'
            results = self.client.search_all(search_query)

            for note in results:
                if note.title == title:
                    # Check notebook match if specified
                    if notebook_id is None or note.parent_id == notebook_id:
                        return note.id

        except Exception as e:
            logger.warning(f"Failed to search for existing note '{title}': {e}")

        return None

    async def _generate_unique_title(
        self, base_title: str, notebook_id: Optional[str]
    ) -> str:
        """Generate a unique title by appending a number.

        Args:
            base_title: Base title to make unique
            notebook_id: Notebook to check uniqueness in

        Returns:
            Unique title
        """
        counter = 1
        while True:
            candidate_title = f"{base_title} ({counter})"
            if not await self._find_existing_note(candidate_title, notebook_id):
                return candidate_title
            counter += 1

            # Safety break to avoid infinite loop
            if counter > 1000:
                return f"{base_title} ({counter})"

    async def _update_note_timestamps(self, note_id: str, note: ImportedNote) -> None:
        """Update note timestamps if preserve_timestamps is enabled.

        Args:
            note_id: ID of the note to update
            note: ImportedNote with timestamp information
        """
        try:
            update_data = {}

            if note.created_time:
                # Convert datetime to milliseconds timestamp
                update_data["created_time"] = int(note.created_time.timestamp() * 1000)

            if note.updated_time:
                update_data["updated_time"] = int(note.updated_time.timestamp() * 1000)

            if update_data:
                self.client.modify_note(note_id, **update_data)

        except Exception as e:
            logger.warning(f"Failed to update timestamps for note {note_id}: {e}")


def get_joplin_client() -> ClientApi:
    """Get a configured joppy client instance.

    Uses the same logic as the main server to ensure consistency.
    """
    try:
        config = JoplinMCPConfig.load()
        if config.token:
            return ClientApi(token=config.token, url=config.base_url)
        else:
            token = os.getenv("JOPLIN_TOKEN")
            if not token:
                raise ValueError(
                    "No token found in config file or JOPLIN_TOKEN environment variable"
                )
            return ClientApi(token=token, url=config.base_url)
    except Exception:
        token = os.getenv("JOPLIN_TOKEN")
        if not token:
            raise ValueError("JOPLIN_TOKEN environment variable is required")
        url = os.getenv("JOPLIN_URL", "http://localhost:41184")
        return ClientApi(token=token, url=url)
