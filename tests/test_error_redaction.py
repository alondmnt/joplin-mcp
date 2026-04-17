"""Tests for token redaction in tool error messages.

joppy appends the Joplin API token to every request URL as a query param,
so any requests.HTTPError raised upstream stringifies the full token
through the URL. with_client_error_handling must redact before the
message reaches MCP clients or logs.
"""

import pytest

from joplin_mcp.fastmcp_server import (
    _redact_token,
    with_client_error_handling,
)


FAKE_TOKEN = "e624dc5b38b4eb06f65dbb85935a19250509d8e63d6369fef391bb76ce93626d"


class TestRedactToken:
    """Tests for the _redact_token helper."""

    def test_redacts_token_query_param(self):
        """Should replace token value with *** in URL query params."""
        text = f"http://localhost:41184/notes/abc?fields=id&token={FAKE_TOKEN}"
        result = _redact_token(text)
        assert FAKE_TOKEN not in result
        assert "token=***" in result
        assert "fields=id" in result  # other params untouched

    def test_redacts_token_when_first_param(self):
        """Should handle token as the first query param (? prefix)."""
        text = f"http://host/path?token={FAKE_TOKEN}&fields=id"
        result = _redact_token(text)
        assert FAKE_TOKEN not in result
        assert "token=***" in result
        assert "fields=id" in result

    def test_redacts_multiple_occurrences(self):
        """Should redact every occurrence if multiple URLs appear."""
        text = (
            f"retry1: http://host/a?token={FAKE_TOKEN} "
            f"retry2: http://host/b?token={FAKE_TOKEN}"
        )
        result = _redact_token(text)
        assert result.count("token=***") == 2
        assert FAKE_TOKEN not in result

    def test_noop_when_no_token(self):
        """Should leave text untouched when no token is present."""
        text = "http://localhost:41184/notes/abc?fields=id"
        assert _redact_token(text) == text

    def test_handles_case_insensitive_token_param(self):
        """Should redact Token= or TOKEN= too."""
        text = f"http://host/p?Token={FAKE_TOKEN}"
        result = _redact_token(text)
        assert FAKE_TOKEN not in result

    def test_does_not_redact_word_token_in_prose(self):
        """Should not touch the word 'token' when it is not a URL param."""
        text = "the token was rotated last week"
        assert _redact_token(text) == text


class TestWithClientErrorHandlingRedaction:
    """End-to-end: errors flowing through the decorator are redacted."""

    @pytest.mark.asyncio
    async def test_httperror_message_is_redacted(self):
        """Token in an exception string must not reach the raised ValueError."""

        @with_client_error_handling("Test Op")
        async def failing_op():
            # Simulate what joppy raises — a stringified HTTPError with full URL
            raise RuntimeError(
                f"404 Client Error: Not Found for url: "
                f"http://localhost:41184/folders/abc?fields=id&token={FAKE_TOKEN}"
            )

        with pytest.raises(ValueError) as exc_info:
            await failing_op()

        message = str(exc_info.value)
        assert FAKE_TOKEN not in message
        assert "token=***" in message
        assert "Test Op failed" in message
        assert "404 Client Error" in message  # useful info preserved

    @pytest.mark.asyncio
    async def test_validation_error_still_reraised_as_is(self):
        """ValueError with 'parameter is required' should pass through untouched."""

        @with_client_error_handling("Test Op")
        async def validation_failure():
            raise ValueError("note_id parameter is required")

        with pytest.raises(ValueError, match="note_id parameter is required"):
            await validation_failure()
