"""Tests for notebook allowlist access control and pathspec matching."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from conftest import make_notebook_map, mock_client_fn

from joplin_mcp.notebook_utils import (
    AllowlistDeniedError,
    filter_accessible_notebooks,
    invalidate_notebook_map_cache,
    is_notebook_accessible,
    validate_notebook_access,
)


class TestNoAllowlistBehavior:
    """Test behavior when no allowlist is configured."""

    def setup_method(self):
        """Clear caches before each test."""
        invalidate_notebook_map_cache()

    def test_allow_all_allows_access(self):
        """When allowlist_entries is ["**"], all notebooks are accessible (no restrictions)."""
        nb_map = make_notebook_map({"nb1": "Projects/Work"})
        client_fn = mock_client_fn(nb_map)

        result = is_notebook_accessible("nb1", allowlist_entries=["**"], client_fn=client_fn)

        assert result is True

    def test_empty_allowlist_denies_access(self):
        """When allowlist_entries is [], is_notebook_accessible returns False (deny all)."""
        nb_map = make_notebook_map({"nb1": "Projects/Work"})
        client_fn = mock_client_fn(nb_map)

        result = is_notebook_accessible("nb1", allowlist_entries=[], client_fn=client_fn)

        assert result is False


class TestExactPathMatching:
    """Test exact path matching in the allowlist."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_exact_path_match(self):
        """Notebook at 'Projects/Work' is accessible when allowlist has 'Projects/Work'."""
        nb_map = make_notebook_map({"nb1": "Projects/Work"})
        client_fn = mock_client_fn(nb_map)

        result = is_notebook_accessible(
            "nb1", allowlist_entries=["Projects/Work"], client_fn=client_fn
        )

        assert result is True

    def test_exact_path_no_match(self):
        """Notebook at 'Personal/Diary' is denied when allowlist only has 'Projects/Work'."""
        nb_map = make_notebook_map({
            "nb1": "Projects/Work",
            "nb2": "Personal/Diary",
        })
        client_fn = mock_client_fn(nb_map)

        result = is_notebook_accessible(
            "nb2", allowlist_entries=["Projects/Work"], client_fn=client_fn
        )

        assert result is False

    def test_notebook_id_not_in_map(self):
        """Notebook ID not found in map returns False."""
        nb_map = make_notebook_map({"nb1": "Projects/Work"})
        client_fn = mock_client_fn(nb_map)

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
        nb_map = make_notebook_map({
            "nb1": "Projects/Work",
            "nb2": "Projects/Personal",
        })
        client_fn = mock_client_fn(nb_map)

        assert is_notebook_accessible(
            "nb1", allowlist_entries=["Projects/*"], client_fn=client_fn
        ) is True

        invalidate_notebook_map_cache()
        assert is_notebook_accessible(
            "nb2", allowlist_entries=["Projects/*"], client_fn=client_fn
        ) is True

    def test_double_star_match(self):
        """Double-star '**' pattern matches at any depth."""
        nb_map = make_notebook_map({
            "nb1": "Projects/Archive",
            "nb2": "Work/Old/Archive",
        })
        client_fn = mock_client_fn(nb_map)

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
        nb_map = make_notebook_map({"nb1": "Projects/Work/Tasks"})
        client_fn = mock_client_fn(nb_map)

        result = is_notebook_accessible(
            "nb1", allowlist_entries=["Projects"], client_fn=client_fn
        )

        assert result is True

    def test_parent_grants_direct_child_access(self):
        """Allowlisting 'Projects' grants access to 'Projects/Work'."""
        nb_map = make_notebook_map({"nb1": "Projects/Work"})
        client_fn = mock_client_fn(nb_map)

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
        nb_map = make_notebook_map({
            "nb1": "Projects/Work",
            "nb2": "Projects/Secret",
        })
        client_fn = mock_client_fn(nb_map)

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
        nb_map = make_notebook_map({"nb1": "Personal/Diary"})
        client_fn = mock_client_fn(nb_map)

        with pytest.raises(AllowlistDeniedError, match="Notebook not accessible"):
            validate_notebook_access(
                "nb1",
                allowlist_entries=["Projects/*"],
                client_fn=client_fn,
            )

    def test_error_message_generic(self):
        """Error message does not reveal notebook name, path, or ID (per D7)."""
        nb_map = make_notebook_map({"abc12345678901234567890123456789": "Secret/Diary"})
        client_fn = mock_client_fn(nb_map)

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
        nb_map = make_notebook_map({"nb1": "Projects/Work"})
        client_fn = mock_client_fn(nb_map)

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
        nb_map = make_notebook_map({
            "nb1": "Projects/Work",
            "nb2": "Personal/Diary",
            "nb3": "Projects/Fun",
        })
        client_fn = mock_client_fn(nb_map)

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
        nb_map = make_notebook_map({"nb1": "Work"})
        client_fn = mock_client_fn(nb_map)
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
        from joplin_mcp.notebook_utils import notebook_resolver

        # Populate caches with dummy data through the resolver's instance attrs
        notebook_resolver._map = {"fake": "data"}
        notebook_resolver._map_built_at = 999999.0
        notebook_resolver._allowlist_positive = "fake_spec"
        notebook_resolver._allowlist_negation = "fake_neg"
        notebook_resolver._allowlist_entries = ["fake"]
        notebook_resolver._allowlist_hex_ids = {"fake"}
        notebook_resolver._allowlist_built_at = 999999.0

        invalidate_notebook_map_cache()

        assert notebook_resolver._map is None
        assert notebook_resolver._map_built_at == 0.0
        assert notebook_resolver._allowlist_positive is None
        assert notebook_resolver._allowlist_negation is None
        assert notebook_resolver._allowlist_entries is None
        assert notebook_resolver._allowlist_hex_ids is None
        assert notebook_resolver._allowlist_built_at == 0.0


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
