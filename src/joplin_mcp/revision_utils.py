"""Revision utilities for creating and reconstructing Joplin note revisions.

Provides diff-match-patch based revision creation (snapshots before destructive
edits) and reconstruction (walking parent chains to rebuild content).
Follows Joplin Desktop's createNoteRevision_ algorithm.
"""

import json
import logging
import time
from typing import Any, Dict, Optional

import diff_match_patch as dmp_module
import joppy.data_types
from joppy.client_api import ClientApi

logger = logging.getLogger(__name__)

# Module-level diff-match-patch instance and patch object type.
# Use non-empty strings to avoid IndexError from patch_make('', '').
_dmp = dmp_module.diff_match_patch()
_PatchObj = type(_dmp.patch_make("", "x")[0])  # diff_match_patch.patch_obj


def _apply_diff(diff_text: str, base: str) -> str:
    """Apply a diff-match-patch diff to a base string.

    Handles both Joplin's JSON format (starts with '[') and legacy format
    (starts with '@@').

    Args:
        diff_text: The diff string in either JSON or legacy format.
        base: The base string to apply the diff to.

    Returns:
        The patched string result.

    Raises:
        ValueError: If diff cannot be parsed or applied.
    """
    if not diff_text or diff_text == "[]":
        return base

    if diff_text.startswith("["):
        # JSON format: list of patch dicts with diffs, start1/2, length1/2
        patch_dicts = json.loads(diff_text)
        patches = []
        for pd in patch_dicts:
            p = _PatchObj()
            p.diffs = [tuple(d) for d in pd["diffs"]]
            p.start1 = pd["start1"]
            p.start2 = pd["start2"]
            p.length1 = pd["length1"]
            p.length2 = pd["length2"]
            patches.append(p)
    else:
        # Legacy format (starts with @@)
        patches = _dmp.patch_fromText(diff_text)

    patched, results = _dmp.patch_apply(patches, base)
    if not all(results):
        failed = sum(1 for r in results if not r)
        logger.warning(
            f"Patch application had {failed} failed hunks out of {len(results)}"
        )
    return patched


def _reconstruct_revision_content(
    client: ClientApi, revision_id: str
) -> Dict[str, Any]:
    """Reconstruct full note content from a revision by walking the parent chain.

    Follows parent_id links back to the first revision, then applies diffs
    sequentially from oldest to newest to reconstruct title, body, and metadata.

    Args:
        client: Configured joppy ClientApi instance.
        revision_id: ID of the revision to reconstruct.

    Returns:
        Dict with keys: 'title', 'body', 'metadata' (parsed metadata_diff).
    """
    # Collect the chain from target revision back to root
    chain = []
    current_id = revision_id

    while current_id:
        rev = client.get_revision(
            current_id,
            fields="id,parent_id,title_diff,body_diff,metadata_diff",
        )
        chain.append(rev)
        current_id = getattr(rev, "parent_id", "") or ""

    # Apply diffs from root (last in chain) forward to target (first in chain)
    chain.reverse()

    title = ""
    body = ""
    metadata: Dict[str, Any] = {}

    for rev in chain:
        title_diff = getattr(rev, "title_diff", "") or ""
        body_diff = getattr(rev, "body_diff", "") or ""
        metadata_diff_str = getattr(rev, "metadata_diff", "") or ""

        if title_diff and title_diff != "[]":
            title = _apply_diff(title_diff, title)
        if body_diff and body_diff != "[]":
            body = _apply_diff(body_diff, body)
        if metadata_diff_str:
            try:
                md = json.loads(metadata_diff_str)
                # Apply "new" fields, remove "deleted" fields
                metadata.update(md.get("new", {}))
                for key in md.get("deleted", []):
                    metadata.pop(key, None)
            except Exception:
                pass

    return {"title": title, "body": body, "metadata": metadata}


def save_note_revision(client: ClientApi, note_id: str) -> Optional[str]:
    """Save current note content as a Joplin revision before overwriting.

    Creates a revision snapshot using Joplin's native revision system.
    Follows Joplin's createNoteRevision_ algorithm:
    - If prior revisions exist: reconstructs previous state, diffs sequentially,
      sets parent_id to chain with existing revisions.
    - If no prior revisions: diffs from empty string (first revision).

    Uses client.add_revision() with corrected millisecond timestamps
    (joppy bug: uses seconds internally -- our kwargs override via **data).

    Args:
        client: Configured joppy ClientApi instance.
        note_id: ID of the note to snapshot.

    Returns:
        Revision ID string on success, None on failure (logs warning).
    """
    try:
        note = client.get_note(
            note_id,
            fields="id,parent_id,title,body,is_todo,todo_completed",
        )

        title = getattr(note, "title", "") or ""
        body = getattr(note, "body", "") or ""
        notebook_id = getattr(note, "parent_id", "") or ""
        is_todo = getattr(note, "is_todo", 0) or 0
        todo_completed = getattr(note, "todo_completed", 0) or 0

        # Find the latest existing revision for this note
        prev_title = ""
        prev_body = ""
        parent_rev_id = ""

        try:
            all_revs = client.get_all_revisions(fields="id,item_id,created_time")
            note_revs = [
                r for r in all_revs if getattr(r, "item_id", "") == note_id
            ]
            if note_revs:
                note_revs.sort(
                    key=lambda r: getattr(r, "created_time", 0), reverse=True
                )
                latest_rev = note_revs[0]
                parent_rev_id = latest_rev.id
                # Reconstruct previous state from the revision chain
                prev_content = _reconstruct_revision_content(client, parent_rev_id)
                prev_title = prev_content["title"]
                prev_body = prev_content["body"]
        except Exception as e:
            logger.debug(
                f"Could not find parent revision for note {note_id}: {e}"
            )

        # Create diffs from previous state to current content
        title_diff = _dmp.patch_toText(_dmp.patch_make(prev_title, title))
        body_diff = _dmp.patch_toText(_dmp.patch_make(prev_body, body))

        # Build metadata_diff: track what changed from previous metadata
        new_metadata = {
            "id": note_id,
            "parent_id": notebook_id,
            "is_todo": is_todo,
            "todo_completed": todo_completed,
            "title": title,
        }
        metadata_diff = json.dumps({"new": new_metadata, "deleted": []})

        now_ms = int(time.time() * 1000)

        revision_data = {
            "item_updated_time": now_ms,
            "item_created_time": now_ms,
            "title_diff": title_diff,
            "body_diff": body_diff,
            "metadata_diff": metadata_diff,
        }
        if parent_rev_id:
            revision_data["parent_id"] = parent_rev_id

        rev_id = client.add_revision(
            item_id=note_id,
            item_type=joppy.data_types.ItemType.NOTE,
            **revision_data,
        )
        logger.info(
            f"Saved revision {rev_id} for note {note_id} "
            f"(parent: {parent_rev_id or 'none'})"
        )
        return rev_id

    except Exception as e:
        logger.warning(f"Failed to save revision for note {note_id}: {e}")
        return None
