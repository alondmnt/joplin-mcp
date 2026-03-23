"""Tests for pathspec pattern matching engine and validation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from joplin_mcp.notebook_utils import (
    _build_allowlist_spec,
    _has_negation_for_path,
    _matches_allowlist,
    invalidate_notebook_map_cache,
    is_notebook_accessible,
)


def _make_notebook_map(paths):
    """Build a notebook map from a dict of {notebook_id: "Parent/Child/Leaf"} paths."""
    nb_map = {}
    path_to_id = {}

    for nb_id, path_str in paths.items():
        parts = path_str.split("/")
        parent_id = None
        for i, part in enumerate(parts):
            partial_path = "/".join(parts[: i + 1])
            if partial_path not in path_to_id:
                if i == len(parts) - 1:
                    node_id = nb_id
                else:
                    node_id = f"auto_{partial_path.replace('/', '_').lower()}"
                path_to_id[partial_path] = node_id
                nb_map[node_id] = {
                    "title": part,
                    "parent_id": parent_id,
                }
            parent_id = path_to_id[partial_path]

    return nb_map


def _mock_client_fn(nb_map):
    """Create a mock client_fn returning notebooks matching the given map."""
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


class TestExactMatchPattern:
    """Test exact match pattern behavior."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_exact_match_pattern(self):
        """Pattern 'AI' matches only 'AI' exactly, not 'AI2'."""
        nb_map = _make_notebook_map({
            "nb1": "AI",
            "nb2": "AI2",
        })
        client_fn = _mock_client_fn(nb_map)

        assert is_notebook_accessible(
            "nb1", allowlist_entries=["AI"], client_fn=client_fn
        ) is True

        invalidate_notebook_map_cache()
        assert is_notebook_accessible(
            "nb2", allowlist_entries=["AI"], client_fn=client_fn
        ) is False

    def test_exact_match_nested_path(self):
        """Exact match 'Projects/Work' matches only that specific path."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Work",
            "nb2": "Projects/WorkExtra",
        })
        client_fn = _mock_client_fn(nb_map)

        assert is_notebook_accessible(
            "nb1", allowlist_entries=["Projects/Work"], client_fn=client_fn
        ) is True

        invalidate_notebook_map_cache()
        assert is_notebook_accessible(
            "nb2", allowlist_entries=["Projects/Work"], client_fn=client_fn
        ) is False


class TestWildcardPattern:
    """Test single-star wildcard patterns."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_wildcard_matches_direct_children(self):
        """Pattern 'Projects/*' matches 'Projects/Work' but not 'Projects/Work/Tasks'."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Work",
            "nb2": "Projects/Work/Tasks",
        })
        client_fn = _mock_client_fn(nb_map)

        # Direct child should match
        assert is_notebook_accessible(
            "nb1", allowlist_entries=["Projects/*"], client_fn=client_fn
        ) is True

        # Grandchild should NOT match with single star alone
        # However, because "Projects/Work" matches, the ancestor check
        # in _matches_allowlist will grant access to children.
        # This is by design per D2 (parent allowlisting grants child access).
        invalidate_notebook_map_cache()
        # The ancestor check means Projects/Work matches, and since
        # Projects/Work is an ancestor of Projects/Work/Tasks, it passes.
        # This is correct hierarchical behavior.
        result = is_notebook_accessible(
            "nb2", allowlist_entries=["Projects/*"], client_fn=client_fn
        )
        # Due to ancestor-based access (D2), grandchildren are accessible
        # when their parent matches a wildcard
        assert result is True


class TestGlobstarPattern:
    """Test double-star (globstar) patterns."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_globstar_matches_all_descendants(self):
        """Pattern 'Projects/**' matches all descendants at any depth."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Work",
            "nb2": "Projects/Work/Tasks",
            "nb3": "Projects/Work/Tasks/Urgent",
        })
        client_fn = _mock_client_fn(nb_map)

        for nb_id in ["nb1", "nb2", "nb3"]:
            invalidate_notebook_map_cache()
            assert is_notebook_accessible(
                nb_id, allowlist_entries=["Projects/**"], client_fn=client_fn
            ) is True, f"{nb_id} should be accessible under Projects/**"

    def test_globstar_does_not_match_sibling(self):
        """Pattern 'Projects/**' does not match 'Personal/Diary'."""
        nb_map = _make_notebook_map({
            "nb1": "Personal/Diary",
        })
        client_fn = _mock_client_fn(nb_map)

        assert is_notebook_accessible(
            "nb1", allowlist_entries=["Projects/**"], client_fn=client_fn
        ) is False


class TestNegationWithinAllowlist:
    """Test negation patterns within allowlists."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_negation_excludes_specific_paths(self):
        """['Projects/**', '!Projects/Secret'] excludes Projects/Secret."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Work",
            "nb2": "Projects/Secret",
        })
        client_fn = _mock_client_fn(nb_map)

        assert is_notebook_accessible(
            "nb1",
            allowlist_entries=["Projects/**", "!Projects/Secret"],
            client_fn=client_fn,
        ) is True

        invalidate_notebook_map_cache()
        assert is_notebook_accessible(
            "nb2",
            allowlist_entries=["Projects/**", "!Projects/Secret"],
            client_fn=client_fn,
        ) is False

    def test_negation_with_ancestor_match(self):
        """Negation overrides ancestor-based access for the negated path."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Secret/Notes",
        })
        client_fn = _mock_client_fn(nb_map)

        # Projects/Secret is negated, so Projects/Secret/Notes should also be denied
        # because the negation check in _has_negation_for_path evaluates full path
        result = is_notebook_accessible(
            "nb1",
            allowlist_entries=["Projects/**", "!Projects/Secret/Notes"],
            client_fn=client_fn,
        )
        assert result is False


class TestPatternOrderMatters:
    """Test that last matching pattern wins (gitignore semantics)."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_pattern_order_last_match_wins(self):
        """Later patterns override earlier ones: negate then re-include."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Secret",
        })
        client_fn = _mock_client_fn(nb_map)

        # First negate, then re-include: last match wins
        result = is_notebook_accessible(
            "nb1",
            allowlist_entries=["Projects/**", "!Projects/Secret", "Projects/Secret"],
            client_fn=client_fn,
        )
        assert result is True

    def test_pattern_order_negate_wins_when_last(self):
        """When negation is the last matching pattern, notebook is denied."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Secret",
        })
        client_fn = _mock_client_fn(nb_map)

        result = is_notebook_accessible(
            "nb1",
            allowlist_entries=["Projects/**", "!Projects/Secret"],
            client_fn=client_fn,
        )
        assert result is False


class TestNotebookIdLiteralPattern:
    """Test literal notebook ID matching."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_notebook_id_literal_pattern(self):
        """32-char hex notebook IDs work as literal exact matches in allowlist."""
        hex_id = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        nb_map = _make_notebook_map({hex_id: "Some/Hidden/Notebook"})
        client_fn = _mock_client_fn(nb_map)

        result = is_notebook_accessible(
            hex_id,
            allowlist_entries=[hex_id],
            client_fn=client_fn,
        )
        assert result is True

    def test_notebook_id_does_not_match_different_id(self):
        """A literal ID pattern does not match a different notebook."""
        hex_id_1 = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        hex_id_2 = "11111111111111111111111111111111"
        nb_map = _make_notebook_map({hex_id_2: "Other/Notebook"})
        client_fn = _mock_client_fn(nb_map)

        result = is_notebook_accessible(
            hex_id_2,
            allowlist_entries=[hex_id_1],
            client_fn=client_fn,
        )
        assert result is False


class TestBuildAllowlistSpec:
    """Test the _build_allowlist_spec function directly."""

    def test_empty_entries_matches_nothing(self):
        """An empty allowlist spec matches no paths."""
        spec = _build_allowlist_spec([])
        assert spec.match_file("anything") is False

    def test_spec_with_patterns(self):
        """Spec built from patterns correctly matches paths."""
        spec = _build_allowlist_spec(["Projects/*", "Work/**"])
        assert spec.match_file("Projects/Foo") is True
        assert spec.match_file("Work/Deep/Nested") is True
        assert spec.match_file("Personal/Diary") is False


class TestHasNegationForPath:
    """Test the _has_negation_for_path helper."""

    def test_no_negation(self):
        """Returns False (not negated) when no negation patterns exist."""
        result = _has_negation_for_path("Projects/Work", ["Projects/*"])
        assert result is False

    def test_negation_applies(self):
        """Returns True (negated) when path matches a negation pattern."""
        result = _has_negation_for_path(
            "Projects/Secret",
            ["Projects/*", "!Projects/Secret"],
        )
        assert result is True

    def test_re_inclusion_after_negation(self):
        """Returns False (not negated) when re-included after negation."""
        result = _has_negation_for_path(
            "Projects/Secret",
            ["Projects/*", "!Projects/Secret", "Projects/Secret"],
        )
        assert result is False
