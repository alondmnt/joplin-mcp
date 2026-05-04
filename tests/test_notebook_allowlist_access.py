"""Tests for notebook allowlist access control and pathspec matching."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from joplin_mcp.notebook_utils import (
    AllowlistDeniedError,
    filter_accessible_notebooks,
    invalidate_notebook_map_cache,
    is_notebook_accessible,
    validate_notebook_access,
)


def _make_notebook_map(paths):
    """Build a notebook map from a dict of {notebook_id: "Parent/Child/Leaf"} paths.

    Returns a map suitable for get_notebook_map_cached, where each notebook ID
    maps to {title, parent_id} and the hierarchy is reconstructed from paths.
    """
    nb_map = {}
    # Track which title at which parent corresponds to which ID
    # We need to assign IDs to intermediate nodes too
    path_to_id = {}

    for nb_id, path_str in paths.items():
        parts = path_str.split("/")
        parent_id = None
        for i, part in enumerate(parts):
            partial_path = "/".join(parts[: i + 1])
            if partial_path not in path_to_id:
                # For the final part, use the given nb_id
                if i == len(parts) - 1:
                    node_id = nb_id
                else:
                    # Generate a synthetic ID for intermediate nodes
                    node_id = f"auto_{partial_path.replace('/', '_').lower()}"
                path_to_id[partial_path] = node_id
                nb_map[node_id] = {
                    "title": part,
                    "parent_id": parent_id,
                }
            parent_id = path_to_id[partial_path]

    return nb_map


def _mock_client_fn(nb_map):
    """Create a mock client_fn that returns a client whose get_all_notebooks
    returns notebook objects matching the given map."""
    notebooks = []
    for nb_id, info in nb_map.items():
        nb = SimpleNamespace(
            id=nb_id,
            title=info["title"],
            parent_id=info["parent_id"] or "",
        )
        notebooks.append(nb)

    mock_client = MagicMock()
    mock_client.get_all_notebooks.return_value = notebooks
    return lambda: mock_client


class TestNoAllowlistBehavior:
    """Test behavior when no allowlist is configured."""

    def setup_method(self):
        """Clear caches before each test."""
        invalidate_notebook_map_cache()

    def test_allow_all_allows_access(self):
        """When allowlist_entries is ["**"], all notebooks are accessible (no restrictions)."""
        nb_map = _make_notebook_map({"nb1": "Projects/Work"})
        client_fn = _mock_client_fn(nb_map)

        result = is_notebook_accessible("nb1", allowlist_entries=["**"], client_fn=client_fn)

        assert result is True

    def test_empty_allowlist_denies_access(self):
        """When allowlist_entries is [], is_notebook_accessible returns False (deny all)."""
        nb_map = _make_notebook_map({"nb1": "Projects/Work"})
        client_fn = _mock_client_fn(nb_map)

        result = is_notebook_accessible("nb1", allowlist_entries=[], client_fn=client_fn)

        assert result is False


class TestExactPathMatching:
    """Test exact path matching in the allowlist."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_exact_path_match(self):
        """Notebook at 'Projects/Work' is accessible when allowlist has 'Projects/Work'."""
        nb_map = _make_notebook_map({"nb1": "Projects/Work"})
        client_fn = _mock_client_fn(nb_map)

        result = is_notebook_accessible(
            "nb1", allowlist_entries=["Projects/Work"], client_fn=client_fn
        )

        assert result is True

    def test_exact_path_no_match(self):
        """Notebook at 'Personal/Diary' is denied when allowlist only has 'Projects/Work'."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Work",
            "nb2": "Personal/Diary",
        })
        client_fn = _mock_client_fn(nb_map)

        result = is_notebook_accessible(
            "nb2", allowlist_entries=["Projects/Work"], client_fn=client_fn
        )

        assert result is False

    def test_notebook_id_not_in_map(self):
        """Notebook ID not found in map returns False."""
        nb_map = _make_notebook_map({"nb1": "Projects/Work"})
        client_fn = _mock_client_fn(nb_map)

        result = is_notebook_accessible(
            "nonexistent", allowlist_entries=["Projects/Work"], client_fn=client_fn
        )

        assert result is False


class TestWildcardMatching:
    """Test wildcard pattern matching."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_wildcard_match(self):
        """Wildcard 'Projects/*' matches direct children of Projects."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Work",
            "nb2": "Projects/Personal",
        })
        client_fn = _mock_client_fn(nb_map)

        assert is_notebook_accessible(
            "nb1", allowlist_entries=["Projects/*"], client_fn=client_fn
        ) is True

        invalidate_notebook_map_cache()
        assert is_notebook_accessible(
            "nb2", allowlist_entries=["Projects/*"], client_fn=client_fn
        ) is True

    def test_double_star_match(self):
        """Double-star '**' pattern matches at any depth."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Archive",
            "nb2": "Work/Old/Archive",
        })
        client_fn = _mock_client_fn(nb_map)

        assert is_notebook_accessible(
            "nb1", allowlist_entries=["**/Archive"], client_fn=client_fn
        ) is True

        invalidate_notebook_map_cache()
        assert is_notebook_accessible(
            "nb2", allowlist_entries=["**/Archive"], client_fn=client_fn
        ) is True


class TestHierarchicalAccess:
    """Test that parent allowlisting grants child access (per D2)."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_parent_grants_child_access(self):
        """Allowlisting 'Projects' grants access to 'Projects/Work/Tasks'."""
        nb_map = _make_notebook_map({"nb1": "Projects/Work/Tasks"})
        client_fn = _mock_client_fn(nb_map)

        result = is_notebook_accessible(
            "nb1", allowlist_entries=["Projects"], client_fn=client_fn
        )

        assert result is True

    def test_parent_grants_direct_child_access(self):
        """Allowlisting 'Projects' grants access to 'Projects/Work'."""
        nb_map = _make_notebook_map({"nb1": "Projects/Work"})
        client_fn = _mock_client_fn(nb_map)

        result = is_notebook_accessible(
            "nb1", allowlist_entries=["Projects"], client_fn=client_fn
        )

        assert result is True


class TestNegationPatterns:
    """Test negation pattern handling."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_negation_pattern(self):
        """Negation '!Projects/Secret' denies access even when 'Projects/*' matches."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Work",
            "nb2": "Projects/Secret",
        })
        client_fn = _mock_client_fn(nb_map)

        # Projects/Work should be accessible
        assert is_notebook_accessible(
            "nb1",
            allowlist_entries=["Projects/*", "!Projects/Secret"],
            client_fn=client_fn,
        ) is True

        # Projects/Secret should be denied
        invalidate_notebook_map_cache()
        assert is_notebook_accessible(
            "nb2",
            allowlist_entries=["Projects/*", "!Projects/Secret"],
            client_fn=client_fn,
        ) is False


class TestValidateNotebookAccess:
    """Test validate_notebook_access raises ValueError for denied notebooks."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_validate_notebook_access_raises(self):
        """validate_notebook_access raises AllowlistDeniedError when notebook is denied."""
        nb_map = _make_notebook_map({"nb1": "Personal/Diary"})
        client_fn = _mock_client_fn(nb_map)

        with pytest.raises(AllowlistDeniedError, match="Notebook not accessible"):
            validate_notebook_access(
                "nb1",
                allowlist_entries=["Projects/*"],
                client_fn=client_fn,
            )

    def test_error_message_generic(self):
        """Error message does not reveal notebook name, path, or ID (per D7)."""
        nb_map = _make_notebook_map({"abc12345678901234567890123456789": "Secret/Diary"})
        client_fn = _mock_client_fn(nb_map)

        with pytest.raises(ValueError) as exc_info:
            validate_notebook_access(
                "abc12345678901234567890123456789",
                allowlist_entries=["Projects/*"],
                client_fn=client_fn,
            )

        error_msg = str(exc_info.value)
        assert "Secret" not in error_msg
        assert "Diary" not in error_msg
        assert "abc12345678901234567890123456789" not in error_msg

    def test_validate_passes_for_accessible_notebook(self):
        """validate_notebook_access does not raise for accessible notebook."""
        nb_map = _make_notebook_map({"nb1": "Projects/Work"})
        client_fn = _mock_client_fn(nb_map)

        # Should not raise
        validate_notebook_access(
            "nb1",
            allowlist_entries=["Projects/*"],
            client_fn=client_fn,
        )


class TestFilterAccessibleNotebooks:
    """Test filter_accessible_notebooks functionality."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_filter_accessible_notebooks(self):
        """filter_accessible_notebooks returns only accessible notebooks."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Work",
            "nb2": "Personal/Diary",
            "nb3": "Projects/Fun",
        })
        client_fn = _mock_client_fn(nb_map)

        notebooks = [
            SimpleNamespace(id="nb1", title="Work"),
            SimpleNamespace(id="nb2", title="Diary"),
            SimpleNamespace(id="nb3", title="Fun"),
        ]

        result = filter_accessible_notebooks(
            notebooks,
            allowlist_entries=["Projects/*"],
            client_fn=client_fn,
        )

        result_ids = [nb.id for nb in result]
        assert "nb1" in result_ids
        assert "nb3" in result_ids
        assert "nb2" not in result_ids

    def test_filter_with_allow_all_returns_all(self):
        """filter_accessible_notebooks returns all notebooks when allowlist is ["**"] (no restrictions)."""
        nb_map = _make_notebook_map({"nb1": "Work"})
        client_fn = _mock_client_fn(nb_map)
        notebooks = [SimpleNamespace(id="nb1", title="Work")]

        result = filter_accessible_notebooks(notebooks, allowlist_entries=["**"], client_fn=client_fn)

        assert len(result) == 1
        assert result[0].id == "nb1"

    def test_filter_with_empty_allowlist_returns_empty(self):
        """filter_accessible_notebooks returns empty list when allowlist is []."""
        notebooks = [SimpleNamespace(id="nb1", title="Work")]

        result = filter_accessible_notebooks(notebooks, allowlist_entries=[])

        assert result == []


class TestCacheInvalidation:
    """Test cache invalidation clears allowlist spec."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_cache_invalidation(self):
        """invalidate_notebook_map_cache clears both notebook map and allowlist spec caches."""
        from joplin_mcp.notebook_utils import _NOTEBOOK_MAP_CACHE, _ALLOWLIST_SPEC_CACHE

        # Populate caches with dummy data
        _NOTEBOOK_MAP_CACHE["built_at"] = 999999.0
        _NOTEBOOK_MAP_CACHE["map"] = {"fake": "data"}
        _ALLOWLIST_SPEC_CACHE["built_at"] = 999999.0
        _ALLOWLIST_SPEC_CACHE["positive_spec"] = "fake_spec"
        _ALLOWLIST_SPEC_CACHE["negation_spec"] = "fake_neg"
        _ALLOWLIST_SPEC_CACHE["entries"] = ["fake"]
        _ALLOWLIST_SPEC_CACHE["hex_ids"] = {"fake"}

        invalidate_notebook_map_cache()

        assert _NOTEBOOK_MAP_CACHE["built_at"] == 0.0
        assert _NOTEBOOK_MAP_CACHE["map"] is None
        assert _ALLOWLIST_SPEC_CACHE["built_at"] == 0.0
        assert _ALLOWLIST_SPEC_CACHE["positive_spec"] is None
        assert _ALLOWLIST_SPEC_CACHE["negation_spec"] is None
        assert _ALLOWLIST_SPEC_CACHE["entries"] is None
        assert _ALLOWLIST_SPEC_CACHE["hex_ids"] is None


class TestStartupValidationNoAutoCreate:
    """Regression test: startup validator must never create notebooks."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_zero_match_does_not_create_notebook(self):
        """When allowlist resolves to zero notebooks, warn but do not auto-create."""
        from unittest.mock import MagicMock

        from joplin_mcp.config import JoplinMCPConfig
        from joplin_mcp.notebook_utils import validate_allowlist_at_startup

        client = MagicMock()
        client.get_all_notebooks.return_value = []
        client.ping.return_value = "JoplinClipperServer"

        config = JoplinMCPConfig(
            token="test_token",
            notebook_allowlist=["NonExistent"],
        )

        validate_allowlist_at_startup(config, client)
        client.add_notebook.assert_not_called()
