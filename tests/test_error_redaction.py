"""Tests for error sanitisation in tool error messages.

joppy stringifies requests.HTTPError with the Joplin response body inline,
which leaks (a) the full API token via the request URL, (b) absolute
filesystem paths from the Joplin Desktop install, and (c) Joplin's internal
TypeScript stack-trace lines. with_client_error_handling must scrub all
three before the message reaches MCP clients or logs.
"""

import pytest

from joplin_mcp.fastmcp_server import (
    _sanitise_error,
    with_client_error_handling,
)


FAKE_TOKEN = "e624dc5b38b4eb06f65dbb85935a19250509d8e63d6369fef391bb76ce93626d"


class TestRedactToken:
    """Token redaction (the original concern)."""

    def test_redacts_token_query_param(self):
        """Should replace token value with *** in URL query params."""
        text = f"http://localhost:41184/notes/abc?fields=id&token={FAKE_TOKEN}"
        result = _sanitise_error(text)
        assert FAKE_TOKEN not in result
        assert "token=***" in result
        assert "fields=id" in result  # other params untouched

    def test_redacts_token_when_first_param(self):
        """Should handle token as the first query param (? prefix)."""
        text = f"http://host/path?token={FAKE_TOKEN}&fields=id"
        result = _sanitise_error(text)
        assert FAKE_TOKEN not in result
        assert "token=***" in result
        assert "fields=id" in result

    def test_redacts_multiple_occurrences(self):
        """Should redact every occurrence if multiple URLs appear."""
        text = (
            f"retry1: http://host/a?token={FAKE_TOKEN} "
            f"retry2: http://host/b?token={FAKE_TOKEN}"
        )
        result = _sanitise_error(text)
        assert result.count("token=***") == 2
        assert FAKE_TOKEN not in result

    def test_noop_when_no_token(self):
        """Should leave text untouched when no token is present."""
        text = "http://localhost:41184/notes/abc?fields=id"
        assert _sanitise_error(text) == text

    def test_handles_case_insensitive_token_param(self):
        """Should redact Token= or TOKEN= too."""
        text = f"http://host/p?Token={FAKE_TOKEN}"
        result = _sanitise_error(text)
        assert FAKE_TOKEN not in result

    def test_does_not_redact_word_token_in_prose(self):
        """Should not touch the word 'token' when it is not a URL param."""
        text = "the token was rotated last week"
        assert _sanitise_error(text) == text


class TestStripStackFrames:
    """JS and Python stack-frame lines must be dropped."""

    def test_strips_js_stack_frame_lines(self):
        """Lines like '    at Func (...)' should be removed entirely."""
        text = (
            "Error: Not found\n"
            "    at handleRequest (Api.js:123:45)\n"
            "    at process._tickCallback (next_tick.js:178:7)"
        )
        result = _sanitise_error(text)
        assert "at handleRequest" not in result
        assert "at process._tickCallback" not in result
        assert "Error: Not found" in result

    def test_strips_python_file_frame_lines(self):
        """Lines like '  File "...", line N, in func' should be removed."""
        text = (
            "RuntimeError: boom\n"
            '  File "module.py", line 42, in some_func\n'
            "    do_thing()"
        )
        result = _sanitise_error(text)
        assert 'File "module.py"' not in result
        assert "RuntimeError: boom" in result

    def test_keeps_prose_starting_with_at(self):
        """A normal sentence beginning with 'at' (no leading whitespace) stays."""
        text = "Failed at startup: missing config"
        assert _sanitise_error(text) == text


class TestStripFilesystemPaths:
    """Absolute paths under common roots leak install location and user."""

    def test_strips_applications_path(self):
        """macOS install paths under /Applications get replaced."""
        text = "at handler (/Applications/Joplin.app/Contents/Resources/lib/x.js:1:2)"
        result = _sanitise_error(text)
        assert "/Applications/Joplin.app" not in result
        assert "<path>" in result

    def test_strips_users_path(self):
        """macOS user home paths get replaced."""
        text = "loaded from /Users/alice/.config/joplin/x.json failed"
        result = _sanitise_error(text)
        assert "/Users/alice" not in result
        assert "<path>" in result

    def test_strips_home_path(self):
        """Linux home paths get replaced."""
        text = "tried /home/bob/snap/joplin/notes.sqlite"
        result = _sanitise_error(text)
        assert "/home/bob" not in result
        assert "<path>" in result

    def test_does_not_strip_url_paths(self):
        """A URL path with /notes/ etc. should not be matched as a filesystem path."""
        text = "GET http://localhost:41184/notes/abc?fields=id"
        result = _sanitise_error(text)
        assert "/notes/abc" in result


class TestSanitiseRealisticJoppyError:
    """End-to-end: a realistic stringified HTTPError gets fully scrubbed."""

    def test_full_joppy_404_payload(self):
        """All three leak types are stripped from one realistic error."""
        text = (
            f"404 Client Error: Not Found for url: "
            f"http://localhost:41184/notes/0000?fields=id,parent_id&token={FAKE_TOKEN}\n"
            "Error: Not found\n"
            "    at handleRequest (/Applications/Joplin.app/Contents/Resources/lib/services/rest/Api.js:123:45)\n"
            "    at process._tickCallback (/Applications/Joplin.app/Contents/Resources/lib/services/internal/process/next_tick.js:178:7)"
        )
        result = _sanitise_error(text)
        assert FAKE_TOKEN not in result
        assert "/Applications/Joplin.app" not in result
        assert " at handleRequest" not in result
        assert " at process._tickCallback" not in result
        # Useful diagnostic info preserved:
        assert "404 Client Error" in result
        assert "token=***" in result


class TestWithClientErrorHandlingRedaction:
    """End-to-end: errors flowing through the decorator are sanitised."""

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
    async def test_stack_trace_is_stripped_through_decorator(self):
        """Absolute paths and stack frames must not reach the raised ValueError."""

        @with_client_error_handling("Test Op")
        async def failing_op():
            raise RuntimeError(
                "500 Server Error\n"
                "    at boom (/Applications/Joplin.app/lib/x.js:1:2)"
            )

        with pytest.raises(ValueError) as exc_info:
            await failing_op()

        message = str(exc_info.value)
        assert "/Applications/Joplin.app" not in message
        assert " at boom" not in message
        assert "500 Server Error" in message

    @pytest.mark.asyncio
    async def test_validation_error_still_reraised_as_is(self):
        """ValueError with 'parameter is required' should pass through untouched."""

        @with_client_error_handling("Test Op")
        async def validation_failure():
            raise ValueError("note_id parameter is required")

        with pytest.raises(ValueError, match="note_id parameter is required"):
            await validation_failure()
