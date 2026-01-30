"""Notebook utilities for path resolution, caching, and lookup."""

import os
import time
from typing import Any, Callable, Dict, List, Optional


# === NOTEBOOK MAP BUILDING ===


def _build_notebook_map(notebooks: List[Any]) -> Dict[str, Dict[str, Optional[str]]]:
    """Build a map of notebook_id -> {title, parent_id}."""
    mapping: Dict[str, Dict[str, Optional[str]]] = {}
    for nb in notebooks or []:
        try:
            nb_id = getattr(nb, "id", None)
            if not nb_id:
                continue
            mapping[nb_id] = {
                "title": getattr(nb, "title", "Untitled"),
                "parent_id": getattr(nb, "parent_id", None),
            }
        except Exception:
            # Be resilient to unexpected notebook structures
            continue
    return mapping


def _compute_notebook_path(
    notebook_id: Optional[str],
    notebooks_map: Dict[str, Dict[str, Optional[str]]],
    sep: str = " / ",
) -> Optional[str]:
    """Compute full notebook path from root to the specified notebook.

    Returns a string like "Parent / Child / Notebook" or None if unavailable.
    """
    if not notebook_id:
        return None

    parts: List[str] = []
    seen: set[str] = set()
    curr = notebook_id
    while curr and curr not in seen:
        seen.add(curr)
        info = notebooks_map.get(curr)
        if not info:
            break
        title = (info.get("title") or "Untitled").strip()
        parts.append(title)
        curr = info.get("parent_id")

    if not parts:
        return None
    return sep.join(reversed(parts))


# === NOTEBOOK MAP CACHE ===


_NOTEBOOK_MAP_CACHE: Dict[str, Any] = {"built_at": 0.0, "map": None}
_DEFAULT_NOTEBOOK_TTL_SECONDS = 90  # sensible default; adjustable via env var


def _get_notebook_cache_ttl() -> int:
    try:
        env_val = os.getenv("JOPLIN_MCP_NOTEBOOK_CACHE_TTL")
        if env_val:
            ttl = int(env_val)
            # Clamp to reasonable bounds to avoid accidental huge/small values
            return max(5, min(ttl, 3600))
    except Exception:
        pass
    return _DEFAULT_NOTEBOOK_TTL_SECONDS


def get_notebook_map_cached(
    force_refresh: bool = False,
    client_fn: Optional[Callable] = None,
) -> Dict[str, Dict[str, Optional[str]]]:
    """Return cached notebook map with TTL; refresh if stale or forced.

    Args:
        force_refresh: Force cache refresh regardless of TTL
        client_fn: Optional function returning joplin client (for dependency injection)
    """
    ttl = _get_notebook_cache_ttl()
    now = time.monotonic()

    if not force_refresh:
        built_at = _NOTEBOOK_MAP_CACHE.get("built_at", 0.0) or 0.0
        cached_map = _NOTEBOOK_MAP_CACHE.get("map")
        if cached_map is not None and (now - built_at) < ttl:
            return cached_map

    # Get client - use provided function or import default
    if client_fn is None:
        from joplin_mcp.fastmcp_server import get_joplin_client
        client_fn = get_joplin_client

    client = client_fn()
    fields_list = "id,title,parent_id"
    notebooks = client.get_all_notebooks(fields=fields_list)
    nb_map = _build_notebook_map(notebooks)
    _NOTEBOOK_MAP_CACHE["map"] = nb_map
    _NOTEBOOK_MAP_CACHE["built_at"] = now
    return nb_map


def invalidate_notebook_map_cache() -> None:
    """Invalidate the cached notebook map so next access refreshes it."""
    _NOTEBOOK_MAP_CACHE["built_at"] = 0.0
    _NOTEBOOK_MAP_CACHE["map"] = None


# === NOTEBOOK PATH RESOLUTION ===


def _find_notebook_suggestions(
    search_term: str,
    notebooks_map: Dict[str, Dict[str, Optional[str]]],
    limit: int = 5,
) -> List[str]:
    """Find notebook paths containing search_term (case-insensitive).

    Args:
        search_term: Term to search for in notebook titles
        notebooks_map: Map of notebook_id -> {title, parent_id}
        limit: Maximum number of suggestions to return

    Returns:
        List of full notebook paths containing the search term
    """
    search_lower = search_term.lower()
    matching_paths = []

    for nb_id, info in notebooks_map.items():
        title = info.get("title", "")
        if search_lower in title.lower():
            full_path = _compute_notebook_path(nb_id, notebooks_map, sep="/")
            if full_path:
                # Sort key: exact match first, then by path length (shorter = more relevant)
                is_exact = title.lower() == search_lower
                matching_paths.append((not is_exact, len(full_path), full_path))

    # Sort by (not_exact, length) and return just the paths
    matching_paths.sort()
    return [path for _, _, path in matching_paths[:limit]]


def _resolve_notebook_by_path(path: str) -> str:
    """Resolve notebook ID from path like 'Parent/Child/Notebook'.

    Args:
        path: Notebook path with '/' separators (e.g., 'Projects/Work/Tasks')

    Returns:
        str: The notebook ID of the final path component

    Raises:
        ValueError: If path is empty or any component not found/ambiguous
    """
    parts = [p.strip() for p in path.split("/") if p.strip()]
    if not parts:
        raise ValueError("Empty notebook path")

    notebooks_map = get_notebook_map_cached(force_refresh=True)

    current_parent: Optional[str] = None
    for part in parts:
        matches = [
            nb_id for nb_id, info in notebooks_map.items()
            if info["title"].lower() == part.lower()
            and (info.get("parent_id") or None) == current_parent
        ]
        if not matches:
            # Provide suggestions for the missing component
            suggestions = _find_notebook_suggestions(part, notebooks_map)
            if suggestions:
                suggestion_str = ", ".join(f"'{s}'" for s in suggestions)
                raise ValueError(
                    f"Notebook '{part}' not found in path '{path}'. "
                    f"Did you mean: {suggestion_str}?"
                )
            raise ValueError(f"Notebook '{part}' not found in path '{path}'")
        if len(matches) > 1:
            raise ValueError(f"Multiple notebooks named '{part}' in path '{path}'")
        current_parent = matches[0]

    return current_parent


def get_notebook_id_by_name(name: str) -> str:
    """Get notebook ID by name or path with helpful error messages.

    Args:
        name: Notebook name or path (e.g., 'Work' or 'Projects/Work/Tasks')

    Returns:
        str: The notebook ID

    Raises:
        ValueError: If notebook not found or multiple matches
    """
    # If path contains '/', resolve by path
    if "/" in name:
        return _resolve_notebook_by_path(name)

    # Otherwise, use flat name matching via generic helper
    from joplin_mcp.fastmcp_server import _get_item_id_by_name, get_joplin_client

    client = get_joplin_client()
    return _get_item_id_by_name(
        name=name,
        item_type="notebook",
        fetch_fn=client.get_all_notebooks,
        fields="id,title,created_time,updated_time,parent_id",
    )
