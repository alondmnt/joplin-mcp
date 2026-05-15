"""Notebook utilities: cache, path resolution, allowlist, and lookup.

The :class:`NotebookResolver` owns the notebook map cache, the compiled
allowlist spec cache, and all path resolution. Mutations performed through
the resolver (``add_notebook``/``modify_notebook``/``delete_notebook``/
``restore_notebook``) invalidate the caches automatically, so callers don't
need to remember to clear state after a write.

The module-level :data:`notebook_resolver` is the default instance used by
tools and server-side code. ``fastmcp_server`` binds the real client factory
to it at startup via :func:`init_resolver`; until then mutation methods raise.

Backward-compatible module-level wrappers (``get_notebook_map_cached``,
``invalidate_notebook_map_cache``, ``is_notebook_accessible``,
``validate_notebook_access``, ``filter_accessible_notebooks``,
``get_accessible_notebook_map``, ``_resolve_notebook_by_path``,
``get_notebook_id_by_name``, ``validate_allowlist_at_startup``) delegate to
the default resolver and accept an optional ``client_fn`` for tests that
want an isolated resolver instance.
"""

import logging
import os
import re
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from joppy.client_api import ClientApi

    from joplin_mcp.config import JoplinMCPConfig

import pathspec

logger = logging.getLogger(__name__)


# === PURE HELPERS ===


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
        # Escape '/' in titles to avoid splitting into fictional path segments
        title = title.replace("/", "∕")  # Unicode fraction slash
        parts.append(title)
        curr = info.get("parent_id")

    if not parts:
        return None
    return sep.join(reversed(parts))


_DEFAULT_NOTEBOOK_TTL_SECONDS = 90  # sensible default; adjustable via env var

# Regex for 32-char hex IDs (Joplin notebook/note IDs)
_HEX_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


def _get_notebook_cache_ttl() -> int:
    """Read cache TTL from JOPLIN_MCP_NOTEBOOK_CACHE_TTL env, clamped to [5, 3600]."""
    try:
        env_val = os.getenv("JOPLIN_MCP_NOTEBOOK_CACHE_TTL")
        if env_val:
            ttl = int(env_val)
            # Clamp to reasonable bounds to avoid accidental huge/small values
            return max(5, min(ttl, 3600))
    except Exception:
        pass
    return _DEFAULT_NOTEBOOK_TTL_SECONDS


def _build_split_specs(
    allowlist_entries: List[str],
) -> tuple:
    """Build separate positive and negation PathSpec objects from allowlist entries.

    Splitting the allowlist into two pre-compiled specs allows a simple matching
    model: any negation match on the path or any ancestor → deny; any positive
    match on the path or any ancestor → allow; negation wins over positive.

    This is intentionally simpler than full gitignore last-match-wins semantics.
    For an access-control allowlist the security failure mode should be over-deny
    rather than over-allow.

    Patterns follow gitwildmatch semantics:
    - 'AI' matches notebooks named 'AI' at any level (basename matching)
    - 'AI/' or '/AI' anchors the match to a specific position
    - 'AI/*' matches direct children of AI
    - 'AI/**' matches all descendants of AI recursively
    - '!Work/Personal' negates the path and all descendants

    Note: Patterns without a '/' match basenames anywhere in the hierarchy
    (standard gitwildmatch behavior). Use 'Parent/Child' paths for exact
    position matching.

    Args:
        allowlist_entries: List of pattern strings (may include '!' prefixed negations).

    Returns:
        Tuple of (positive_spec, negation_spec, hex_ids_set).
    """
    positive = [e for e in allowlist_entries if not e.startswith("!")]
    negation = [e[1:] for e in allowlist_entries if e.startswith("!")]
    hex_ids = {
        e.lower() for e in allowlist_entries if _HEX_ID_RE.match(e)
    }

    positive_spec = pathspec.PathSpec.from_lines("gitwildmatch", positive)
    negation_spec = pathspec.PathSpec.from_lines("gitwildmatch", negation)
    return positive_spec, negation_spec, hex_ids


def _path_or_ancestor_matches(spec: pathspec.PathSpec, path: str) -> bool:
    """Return True if spec matches the path or any of its ancestor prefixes."""
    if spec.match_file(path):
        return True
    parts = path.split("/")
    for i in range(1, len(parts)):
        if spec.match_file("/".join(parts[:i])):
            return True
    return False


def _matches_allowlist(
    notebook_path: str,
    notebook_id: str,
    positive_spec: pathspec.PathSpec,
    negation_spec: pathspec.PathSpec,
    hex_ids: set,
) -> bool:
    """Check if a notebook path or ID matches the allowlist.

    Matching model (negation wins, covers descendants):
    1. If any negation pattern matches the path or any ancestor → deny.
    2. If any positive pattern matches the path or any ancestor → allow.
    3. If the notebook ID is a literal hex ID in the allowlist → allow.
    4. Otherwise → deny.

    Args:
        notebook_path: Full path like 'Projects/Work/Tasks'.
        notebook_id: The notebook's ID (32-char hex).
        positive_spec: Compiled PathSpec from non-negated patterns.
        negation_spec: Compiled PathSpec from negated patterns (without '!').
        hex_ids: Set of lowercase hex IDs from the allowlist.

    Returns:
        True if the notebook is accessible.
    """
    # Negation wins: if any negation matches path or ancestor, deny
    if _path_or_ancestor_matches(negation_spec, notebook_path):
        return False

    # Positive match on path or ancestor
    if _path_or_ancestor_matches(positive_spec, notebook_path):
        return True

    # Literal hex ID match (case-insensitive)
    if notebook_id.lower() in hex_ids:
        return True

    return False


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


class AllowlistDeniedError(ValueError):
    """Raised when a notebook access check fails due to the allowlist.

    Subclass of ValueError so existing error handlers that catch ValueError
    continue to work. Callers that need to distinguish allowlist denials
    from other validation errors can catch this type specifically.
    """


# === RESOLVER ===


def _uninitialized_client_factory() -> "ClientApi":
    """Placeholder factory raised when init_resolver hasn't been called."""
    raise RuntimeError(
        "NotebookResolver client factory not initialized; "
        "call init_resolver(client_factory) before performing notebook operations."
    )


class NotebookResolver:
    """Owns the notebook map cache, allowlist spec cache, and resolution.

    Construct with a client factory; the resolver pulls a Joplin client when
    it needs to refresh the cache or perform a mutation. Mutations
    (``add_notebook``, ``modify_notebook``, ``delete_notebook``,
    ``restore_notebook``) invalidate the caches automatically so callers
    don't carry the burden of remembering.

    The resolver is stateful: one instance holds one map + allowlist cache
    pair. Tests that want isolation can construct their own instance with a
    mock client factory rather than mutating the default.
    """

    def __init__(
        self,
        client_factory: Optional[Callable[[], "ClientApi"]] = None,
    ) -> None:
        self._client_factory: Callable[[], "ClientApi"] = (
            client_factory or _uninitialized_client_factory
        )
        self._map: Optional[Dict[str, Dict[str, Optional[str]]]] = None
        self._map_built_at: float = 0.0
        self._allowlist_entries: Optional[List[str]] = None
        self._allowlist_positive: Optional[pathspec.PathSpec] = None
        self._allowlist_negation: Optional[pathspec.PathSpec] = None
        self._allowlist_hex_ids: Optional[set] = None
        self._allowlist_built_at: float = 0.0

    # === Cache control ===

    def invalidate(self) -> None:
        """Reset both the notebook map cache and the allowlist spec cache."""
        self._map = None
        self._map_built_at = 0.0
        self._allowlist_entries = None
        self._allowlist_positive = None
        self._allowlist_negation = None
        self._allowlist_hex_ids = None
        self._allowlist_built_at = 0.0

    # === Read methods ===

    def get_map(
        self, force_refresh: bool = False
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Return the cached notebook map; refresh if stale or forced."""
        ttl = _get_notebook_cache_ttl()
        now = time.monotonic()
        if (
            not force_refresh
            and self._map is not None
            and (now - self._map_built_at) < ttl
        ):
            return self._map

        client = self._client_factory()
        notebooks = client.get_all_notebooks(fields="id,title,parent_id")
        nb_map = _build_notebook_map(notebooks)
        self._map = nb_map
        self._map_built_at = now
        return nb_map

    def _get_allowlist_specs(
        self,
        allowlist_entries: List[str],
        force_refresh: bool = False,
    ) -> tuple:
        """Return cached (positive_spec, negation_spec, hex_ids), rebuilding if stale."""
        if not allowlist_entries:
            empty = pathspec.PathSpec.from_lines("gitwildmatch", [])
            return empty, empty, set()

        ttl = _get_notebook_cache_ttl()
        now = time.monotonic()

        if not force_refresh:
            if (
                self._allowlist_positive is not None
                and self._allowlist_entries == allowlist_entries
                and (now - self._allowlist_built_at) < ttl
            ):
                return (
                    self._allowlist_positive,
                    self._allowlist_negation,
                    self._allowlist_hex_ids,
                )

        positive_spec, negation_spec, hex_ids = _build_split_specs(allowlist_entries)
        self._allowlist_positive = positive_spec
        self._allowlist_negation = negation_spec
        self._allowlist_hex_ids = hex_ids
        self._allowlist_entries = list(allowlist_entries)
        self._allowlist_built_at = now
        return positive_spec, negation_spec, hex_ids

    def get_accessible_map(
        self,
        allowlist_entries: Optional[List[str]] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Dict[str, Optional[str]]]:
        """Return the notebook map filtered by allowlist (ancestors included).

        When ``allowlist_entries`` is None or empty, returns the full cached map.
        Ancestors of accessible notebooks are kept so nested allowlist entries
        (e.g. ``Personal/Work`` requires ``Personal`` in the map) resolve.
        """
        nb_map = self.get_map(force_refresh=force_refresh)
        if not allowlist_entries:
            return nb_map

        positive_spec, negation_spec, hex_ids = self._get_allowlist_specs(
            allowlist_entries
        )

        visible: set = set()
        for nb_id in nb_map:
            path = _compute_notebook_path(nb_id, nb_map, sep="/")
            if not path:
                continue
            if _matches_allowlist(
                path, nb_id, positive_spec, negation_spec, hex_ids
            ):
                curr = nb_id
                while curr and curr not in visible:
                    visible.add(curr)
                    curr = (nb_map.get(curr) or {}).get("parent_id")

        return {nb_id: info for nb_id, info in nb_map.items() if nb_id in visible}

    def is_accessible(
        self,
        notebook_id: str,
        allowlist_entries: List[str],
        force_refresh: bool = False,
    ) -> bool:
        """Check if a notebook is accessible under the current allowlist.

        Empty allowlist denies all.
        """
        if not allowlist_entries:
            return False

        positive_spec, negation_spec, hex_ids = self._get_allowlist_specs(
            allowlist_entries, force_refresh=force_refresh
        )

        nb_map = self.get_map(force_refresh=force_refresh)

        if notebook_id not in nb_map:
            logger.debug(
                "Notebook ID not found in map for allowlist check: %s",
                notebook_id,
            )
            return False

        notebook_path = _compute_notebook_path(notebook_id, nb_map, sep="/")
        if not notebook_path:
            return False

        return _matches_allowlist(
            notebook_path, notebook_id, positive_spec, negation_spec, hex_ids
        )

    def validate_access(
        self,
        notebook_id: str,
        allowlist_entries: List[str],
        force_refresh: bool = False,
    ) -> None:
        """Raise ``AllowlistDeniedError`` if a notebook is not accessible.

        Error messages are intentionally generic to avoid revealing notebook
        details (D7).
        """
        if not self.is_accessible(
            notebook_id,
            allowlist_entries=allowlist_entries,
            force_refresh=force_refresh,
        ):
            raise AllowlistDeniedError("Notebook not accessible")

    def filter_accessible(
        self,
        notebooks: List[Any],
        allowlist_entries: List[str],
    ) -> List[Any]:
        """Filter a list of notebooks to only those accessible under the allowlist.

        Empty allowlist denies all (returns empty list).
        """
        if not allowlist_entries:
            return []

        result = []
        for nb in notebooks:
            nb_id = getattr(nb, "id", None) or (
                nb.get("id") if isinstance(nb, dict) else None
            )
            if nb_id and self.is_accessible(
                nb_id, allowlist_entries=allowlist_entries
            ):
                result.append(nb)
        return result

    def resolve_by_path(
        self,
        path: str,
        allowlist_entries: Optional[List[str]] = None,
    ) -> str:
        """Resolve a notebook ID from a path like 'Parent/Child/Notebook'.

        When ``allowlist_entries`` is provided the map is filtered first so
        suggestions can't leak denied notebook names.
        """
        parts = [p.strip() for p in path.split("/") if p.strip()]
        if not parts:
            raise ValueError("Empty notebook path")

        notebooks_map = self.get_accessible_map(
            allowlist_entries=allowlist_entries, force_refresh=True
        )

        current_parent: Optional[str] = None
        for part in parts:
            matches = [
                nb_id for nb_id, info in notebooks_map.items()
                if info["title"].lower() == part.lower()
                and (info.get("parent_id") or None) == current_parent
            ]
            if not matches:
                suggestions = _find_notebook_suggestions(part, notebooks_map)
                if suggestions:
                    suggestion_str = ", ".join(f"'{s}'" for s in suggestions)
                    raise ValueError(
                        f"Notebook '{part}' not found in path '{path}'. "
                        f"Did you mean: {suggestion_str}?"
                    )
                raise ValueError(f"Notebook '{part}' not found in path '{path}'")
            if len(matches) > 1:
                raise ValueError(
                    f"Multiple notebooks named '{part}' in path '{path}'"
                )
            current_parent = matches[0]

        return current_parent

    def resolve_by_name(
        self,
        name: str,
        allowlist_entries: Optional[List[str]] = None,
    ) -> str:
        """Resolve a notebook ID by name or path with helpful error messages."""
        if "/" in name:
            return self.resolve_by_path(name, allowlist_entries=allowlist_entries)

        notebooks_map = self.get_accessible_map(
            allowlist_entries=allowlist_entries, force_refresh=True
        )

        name_lower = name.lower()
        matches = [
            nb_id for nb_id, info in notebooks_map.items()
            if (info.get("title") or "").lower() == name_lower
        ]

        if not matches:
            suggestions = _find_notebook_suggestions(name, notebooks_map)
            if suggestions:
                suggestion_str = ", ".join(f"'{s}'" for s in suggestions)
                raise ValueError(
                    f"Notebook '{name}' not found. "
                    f"Did you mean: {suggestion_str}?"
                )
            raise ValueError(f"Notebook '{name}' not found")

        if len(matches) > 1:
            paths = [
                _compute_notebook_path(nb_id, notebooks_map, sep="/")
                or (notebooks_map[nb_id].get("title") or "Untitled")
                for nb_id in matches
            ]
            paths_str = ", ".join(f"'{p}'" for p in paths)
            raise ValueError(
                f"Multiple notebooks found with name '{name}'. "
                f"Use full path to specify: {paths_str}"
            )

        return matches[0]

    # === Mutation methods (auto-invalidate) ===

    def add_notebook(self, **kwargs: Any) -> Any:
        """Create a notebook via the client and invalidate caches."""
        client = self._client_factory()
        result = client.add_notebook(**kwargs)
        self.invalidate()
        return result

    def modify_notebook(self, notebook_id: str, **fields: Any) -> None:
        """Update a notebook via the client and invalidate caches."""
        client = self._client_factory()
        client.modify_notebook(notebook_id, **fields)
        self.invalidate()

    def delete_notebook(self, notebook_id: str) -> None:
        """Soft-delete a notebook via the client and invalidate caches."""
        client = self._client_factory()
        client.delete_notebook(notebook_id)
        self.invalidate()

    # === Startup ===

    def validate_allowlist_at_startup(
        self,
        config: "JoplinMCPConfig",
        client: "ClientApi",
    ) -> None:
        """Validate and log allowlist configuration at server startup.

        Resolves each allowlist entry, logs accessible notebooks, warns about
        non-existent entries, and pre-populates caches. Never raises — the
        server always starts successfully regardless of allowlist validity.
        """
        try:
            self._validate_allowlist_at_startup_inner(config, client)
        except Exception:
            # Safety net: never prevent server startup (D3, D10)
            logger.warning(
                "Unexpected error during allowlist validation; "
                "server will continue without validated allowlist",
                exc_info=True,
            )

    def _validate_allowlist_at_startup_inner(
        self,
        config: "JoplinMCPConfig",
        client: "ClientApi",
    ) -> None:
        """Inner implementation for validate_allowlist_at_startup."""
        allowlist = config.notebook_allowlist

        # No allowlist configured — all notebooks accessible
        if not config.has_notebook_allowlist:
            logger.info(
                "No notebook allowlist configured -- all notebooks accessible"
            )
            return

        # Allowlist is configured (could be empty list or populated)
        if not allowlist:
            logger.warning(
                "Notebook allowlist is configured but empty -- "
                "no notebooks are accessible"
            )

        # Build a fresh notebook map from the explicit client, then populate
        # our cache so subsequent reads through the resolver hit it warm.
        notebooks = client.get_all_notebooks(fields="id,title,parent_id")
        nb_map = _build_notebook_map(notebooks)
        self._map = nb_map
        self._map_built_at = time.monotonic()

        # Build reverse lookup: path -> id
        path_to_id: Dict[str, str] = {}
        for nb_id in nb_map:
            path = _compute_notebook_path(nb_id, nb_map, sep="/")
            if path:
                path_to_id[path] = nb_id

        resolved_entries: List[str] = []
        unresolved_entries: List[str] = []

        for entry in allowlist:
            entry_stripped = entry.strip()
            if not entry_stripped:
                continue

            # Negation patterns (e.g. "!Secret") — just log them
            if entry_stripped.startswith("!"):
                logger.debug(
                    "Allowlist negation pattern: %s", entry_stripped
                )
                resolved_entries.append(entry_stripped)
                continue

            # Check if entry is a 32-char hex ID
            if _HEX_ID_RE.match(entry_stripped):
                if entry_stripped in nb_map:
                    path = _compute_notebook_path(
                        entry_stripped, nb_map, sep="/"
                    )
                    logger.debug(
                        "Allowlist entry resolved: ID %s -> %s",
                        entry_stripped,
                        path or "(root)",
                    )
                    resolved_entries.append(entry_stripped)
                else:
                    logger.warning(
                        "Allowlist entry not found: ID %s does not match "
                        "any existing notebook",
                        entry_stripped,
                    )
                    unresolved_entries.append(entry_stripped)
                continue

            # Check if entry is a glob pattern
            has_glob = any(c in entry_stripped for c in ("*", "?"))
            if has_glob:
                pattern_spec = pathspec.PathSpec.from_lines(
                    "gitwildmatch", [entry_stripped]
                )
                match_count = sum(
                    1 for p in path_to_id if pattern_spec.match_file(p)
                )
                logger.debug(
                    "Allowlist glob pattern: %s (matches %d notebook%s)",
                    entry_stripped,
                    match_count,
                    "" if match_count == 1 else "s",
                )
                if match_count == 0:
                    logger.warning(
                        "Allowlist glob pattern matches no existing "
                        "notebooks: %s",
                        entry_stripped,
                    )
                    unresolved_entries.append(entry_stripped)
                else:
                    resolved_entries.append(entry_stripped)
                continue

            # Literal path — try exact match first, then case-insensitive
            if entry_stripped in path_to_id:
                logger.debug(
                    "Allowlist entry resolved: '%s' -> ID %s",
                    entry_stripped,
                    path_to_id[entry_stripped],
                )
                resolved_entries.append(entry_stripped)
            else:
                lower_entry = entry_stripped.lower()
                matched = False
                for path, nb_id in path_to_id.items():
                    if path.lower() == lower_entry:
                        logger.debug(
                            "Allowlist entry resolved (case-insensitive): "
                            "'%s' -> '%s' (ID %s)",
                            entry_stripped,
                            path,
                            nb_id,
                        )
                        resolved_entries.append(entry_stripped)
                        matched = True
                        break
                if not matched:
                    logger.warning(
                        "Allowlist entry not found: '%s' does not match "
                        "any existing notebook path",
                        entry_stripped,
                    )
                    unresolved_entries.append(entry_stripped)

        # Pre-populate the allowlist spec cache (D6)
        self._get_allowlist_specs(allowlist, force_refresh=True)

        # Summary logging
        if resolved_entries:
            logger.info(
                "Allowlist validation complete: %d resolved, %d unresolved",
                len(resolved_entries),
                len(unresolved_entries),
            )
        elif allowlist:
            logger.warning(
                "All %d allowlist entries are unresolved", len(allowlist)
            )

        # Check how many notebooks are actually accessible
        all_notebooks = client.get_all_notebooks(fields="id,title,parent_id")
        accessible = self.filter_accessible(
            all_notebooks, allowlist_entries=allowlist
        )

        if len(accessible) == 0:
            logger.warning(
                "Allowlist is configured but resolves to zero accessible "
                "notebooks -- check your allowlist configuration"
            )
        else:
            logger.info(
                "%d notebook%s accessible under current allowlist",
                len(accessible),
                "" if len(accessible) == 1 else "s",
            )


# Default resolver instance; ``init_resolver`` binds the real client factory.
notebook_resolver = NotebookResolver()


def init_resolver(
    client_factory: Callable[[], "ClientApi"],
) -> NotebookResolver:
    """Bind a Joplin client factory to the default resolver.

    Called by ``fastmcp_server`` once ``get_joplin_client`` is defined so the
    resolver can perform mutations and refresh its cache.
    """
    notebook_resolver._client_factory = client_factory
    return notebook_resolver


# === Backward-compatible module-level wrappers ===
#
# Tests and external callers reach the resolver through these wrappers.
# Passing ``client_fn`` produces a fresh isolated resolver so test fixtures
# don't pollute the module-level cache.


def _select_resolver(
    client_fn: Optional[Callable[[], "ClientApi"]],
) -> NotebookResolver:
    """Return the default resolver, or a fresh one bound to ``client_fn``."""
    if client_fn is None:
        return notebook_resolver
    return NotebookResolver(client_fn)


def get_notebook_map_cached(
    force_refresh: bool = False,
    client_fn: Optional[Callable[[], "ClientApi"]] = None,
) -> Dict[str, Dict[str, Optional[str]]]:
    """Return cached notebook map (TTL-bounded). Delegates to the resolver."""
    return _select_resolver(client_fn).get_map(force_refresh=force_refresh)


def invalidate_notebook_map_cache() -> None:
    """Invalidate the default resolver's notebook map and allowlist caches."""
    notebook_resolver.invalidate()


def is_notebook_accessible(
    notebook_id: str,
    allowlist_entries: List[str],
    force_refresh: bool = False,
    client_fn: Optional[Callable[[], "ClientApi"]] = None,
) -> bool:
    """Check whether a notebook is accessible under the allowlist."""
    return _select_resolver(client_fn).is_accessible(
        notebook_id,
        allowlist_entries=allowlist_entries,
        force_refresh=force_refresh,
    )


def validate_notebook_access(
    notebook_id: str,
    allowlist_entries: List[str],
    force_refresh: bool = False,
    client_fn: Optional[Callable[[], "ClientApi"]] = None,
) -> None:
    """Raise ``AllowlistDeniedError`` if a notebook is not accessible."""
    _select_resolver(client_fn).validate_access(
        notebook_id,
        allowlist_entries=allowlist_entries,
        force_refresh=force_refresh,
    )


def filter_accessible_notebooks(
    notebooks: List[Any],
    allowlist_entries: List[str],
    client_fn: Optional[Callable[[], "ClientApi"]] = None,
) -> List[Any]:
    """Filter notebooks to only those accessible under the allowlist."""
    return _select_resolver(client_fn).filter_accessible(
        notebooks, allowlist_entries=allowlist_entries
    )


def get_accessible_notebook_map(
    allowlist_entries: Optional[List[str]] = None,
    force_refresh: bool = False,
    client_fn: Optional[Callable[[], "ClientApi"]] = None,
) -> Dict[str, Dict[str, Optional[str]]]:
    """Return the notebook map filtered by allowlist (ancestors included)."""
    return _select_resolver(client_fn).get_accessible_map(
        allowlist_entries=allowlist_entries, force_refresh=force_refresh
    )


def _resolve_notebook_by_path(path: str) -> str:
    """Resolve a notebook ID from a slash-delimited path.

    Reads the configured allowlist from ``fastmcp_server._module_config`` so
    suggestions and errors can't leak denied notebook names.
    """
    from joplin_mcp.fastmcp_server import _module_config

    allowlist = (
        _module_config.notebook_allowlist
        if _module_config.has_notebook_allowlist
        else None
    )
    return notebook_resolver.resolve_by_path(path, allowlist_entries=allowlist)


def get_notebook_id_by_name(name: str) -> str:
    """Resolve a notebook ID by name or path with helpful error messages.

    Reads the configured allowlist from ``fastmcp_server._module_config`` so
    suggestions and errors can't leak denied notebook names.
    """
    from joplin_mcp.fastmcp_server import _module_config

    allowlist = (
        _module_config.notebook_allowlist
        if _module_config.has_notebook_allowlist
        else None
    )
    return notebook_resolver.resolve_by_name(name, allowlist_entries=allowlist)


def validate_allowlist_at_startup(
    config: "JoplinMCPConfig",
    client: "ClientApi",
) -> None:
    """Validate and log allowlist configuration at server startup."""
    notebook_resolver.validate_allowlist_at_startup(config, client)
