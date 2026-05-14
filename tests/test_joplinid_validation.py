"""Cover JoplinIdType validation via the MCP .run({...}) path.

Most tool tests call _get_tool_fn(tool)(...) and bypass Pydantic, so the
min_length=32, max_length=32 constraints on JoplinIdType are not actually
exercised. These tests go through tool.run({...}) — the real MCP path —
so a regression that widened the type or dropped a body validate call
would not slip through.

get_note is the canary: representative of every notes.py / trash.py tool
that combines a JoplinIdType param with a body validate_joplin_id() call.
The other tools share the same wiring, so testing each one would be
redundant. tag_note has a distinct Pydantic shape (Union[JoplinIdType,
List[JoplinIdType]]) and gets its own check.
"""

import pytest
from pydantic import ValidationError


class TestJoplinIdValidation:
    """Sharp, evergreen coverage of JoplinIdType through the MCP entry path."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_id", ["", "short", "x" * 33])
    async def test_pydantic_length_rejects_via_run(self, bad_id):
        """Pydantic enforces 32-char length at parse time, before the body runs."""
        from joplin_mcp.tools.notes import get_note

        with pytest.raises(ValidationError, match=r"(at least 32|at most 32)"):
            await get_note.run({"note_id": bad_id})

    @pytest.mark.asyncio
    async def test_body_hex_check_fires_via_run(self):
        """32-char non-hex passes Pydantic; body validate_joplin_id then rejects."""
        from joplin_mcp.tools.notes import get_note

        with pytest.raises(ValueError, match="hexadecimal"):
            await get_note.run({"note_id": "g" * 32})

    @pytest.mark.asyncio
    async def test_union_list_form_still_validates(self):
        """tag_note accepts Union[JoplinIdType, List[JoplinIdType]] — the list branch validates too."""
        from joplin_mcp.tools.tags import tag_note

        with pytest.raises(ValidationError, match="at least 32"):
            await tag_note.run({"note_id": ["short"], "tag_name": "Work"})
