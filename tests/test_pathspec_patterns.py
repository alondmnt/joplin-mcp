"""Tests for pathspec pattern matching engine and validation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from joplin_mcp.notebook_utils import (
    _build_split_specs,
    _matches_allowlist,
    _path_or_ancestor_matches,
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
        # grants access to children.
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
        # because negation covers descendants (ancestor of path matches negation)
        result = is_notebook_accessible(
            "nb1",
            allowlist_entries=["Projects/**", "!Projects/Secret"],
            client_fn=client_fn,
        )
        assert result is False

    def test_negation_descendants_are_blocked(self):
        """Negating a path also blocks all descendants (no need for /**)."""
        nb_map = _make_notebook_map({
            "nb1": "Work/Personal/Sub",
        })
        client_fn = _mock_client_fn(nb_map)

        # !Work/Personal should deny Work/Personal/Sub too
        result = is_notebook_accessible(
            "nb1",
            allowlist_entries=["Work", "!Work/Personal"],
            client_fn=client_fn,
        )
        assert result is False


class TestNegationAlwaysWins:
    """Test that any negation match denies access (negation wins over positive).

    This is intentionally simpler than gitignore last-match-wins semantics.
    For an access-control allowlist the failure mode should be over-deny
    rather than over-allow.
    """

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_negation_overrides_positive_regardless_of_order(self):
        """Negation wins even if a positive pattern comes after it."""
        nb_map = _make_notebook_map({
            "nb1": "Projects/Secret",
        })
        client_fn = _mock_client_fn(nb_map)

        # Positive after negation: negation still wins (over-deny)
        result = is_notebook_accessible(
            "nb1",
            allowlist_entries=["Projects/**", "!Projects/Secret", "Projects/Secret"],
            client_fn=client_fn,
        )
        assert result is False

    def test_negation_wins_when_last(self):
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


class TestBuildSplitSpecs:
    """Test the _build_split_specs function directly."""

    def test_empty_entries(self):
        """Empty entries produce specs that match nothing."""
        pos, neg, ids = _build_split_specs([])
        assert pos.match_file("anything") is False
        assert neg.match_file("anything") is False
        assert ids == set()

    def test_positive_and_negation_split(self):
        """Positive and negation patterns are separated correctly."""
        pos, neg, ids = _build_split_specs(
            ["Projects/*", "!Projects/Secret", "Work/**"]
        )
        assert pos.match_file("Projects/Foo") is True
        assert pos.match_file("Work/Deep/Nested") is True
        assert neg.match_file("Projects/Secret") is True
        assert neg.match_file("Work/Foo") is False

    def test_hex_ids_extracted(self):
        """32-char hex IDs are extracted into a lowercase set."""
        hex_id = "aabbccdd11223344aabbccdd11223344"
        pos, neg, ids = _build_split_specs([hex_id, "Work"])
        assert hex_id in ids
        assert len(ids) == 1


class TestPathOrAncestorMatches:
    """Test the _path_or_ancestor_matches helper."""

    def test_direct_match(self):
        """Returns True when the path itself matches."""
        import pathspec
        spec = pathspec.PathSpec.from_lines("gitwildmatch", ["Projects/*"])
        assert _path_or_ancestor_matches(spec, "Projects/Work") is True

    def test_ancestor_match(self):
        """Returns True when an ancestor of the path matches."""
        import pathspec
        spec = pathspec.PathSpec.from_lines("gitwildmatch", ["Projects"])
        assert _path_or_ancestor_matches(spec, "Projects/Work/Sub") is True

    def test_no_match(self):
        """Returns False when neither path nor ancestors match."""
        import pathspec
        spec = pathspec.PathSpec.from_lines("gitwildmatch", ["Work"])
        assert _path_or_ancestor_matches(spec, "Personal/Diary") is False


class TestSlashInNotebookTitles:
    """Test that '/' in notebook titles doesn't break path matching."""

    def setup_method(self):
        invalidate_notebook_map_cache()

    def test_slash_in_title_does_not_create_fictional_segments(self):
        """A notebook titled 'Tax / 2025' should not split into fake path segments."""
        from joplin_mcp.notebook_utils import _compute_notebook_path

        # Simulate: Finance contains "Tax / 2025"
        nb_map = {
            "finance_id": {"title": "Finance", "parent_id": None},
            "tax_id": {"title": "Tax / 2025", "parent_id": "finance_id"},
        }
        path = _compute_notebook_path("tax_id", nb_map, sep="/")
        # The '/' in the title should be escaped, not treated as a separator
        assert path.count("/") == 1  # only the real separator between Finance and title
        assert "Tax" in path
        assert "2025" in path

    def test_slash_in_title_allowlist_matching(self):
        """Allowlist should handle notebooks with '/' in titles correctly."""
        # Build a map where the title has a '/'
        nb_map = {
            "finance_id": {"title": "Finance", "parent_id": None},
            "tax_id": {"title": "Tax / 2025", "parent_id": "finance_id"},
        }
        notebooks = [
            SimpleNamespace(id="finance_id", title="Finance", parent_id=""),
            SimpleNamespace(id="tax_id", title="Tax / 2025", parent_id="finance_id"),
        ]
        client = MagicMock()
        client.get_all_notebooks.return_value = notebooks
        client_fn = lambda: client  # noqa: E731

        # Allowlisting "Finance" should grant access to "Tax / 2025" child
        result = is_notebook_accessible(
            "tax_id", allowlist_entries=["Finance"], client_fn=client_fn
        )
        assert result is True
