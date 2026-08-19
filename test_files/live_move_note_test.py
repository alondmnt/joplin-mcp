"""Live end-to-end test of the update_note `notebook_name` move parameter (#21).

Exercises:
- update_note(notebook_name=...) moves a note between notebooks
- combined update (title + notebook_name) applies both in one call
- path-style notebook_name ("parent/child") resolves correctly
- invalid notebook_name raises ValueError and does not mutate the note

Creates two isolated "mcp_live_test_<ts>_{a,b}" notebooks plus a "parent/child"
hierarchy so we never touch real data. Trashes them at the end — manual purge via
Joplin UI if desired.
"""

import asyncio
import sys
import time

sys.path.insert(0, "src")

from joplin_mcp.tools.notes import (
    create_note,
    find_notes_in_notebook,
    get_note,
    update_note,
)
from joplin_mcp.tools.notebooks import (
    create_notebook,
    delete_notebook,
)


def fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool


def show(label, result):
    print(f"\n--- {label} ---")
    print(result)


def assert_contains(label, text, needle):
    if needle in text:
        print(f"[OK] {label}: contains {needle!r}")
    else:
        print(f"[FAIL] {label}: missing {needle!r} in: {text[:300]}")


def assert_not_contains(label, text, needle):
    if needle not in text:
        print(f"[OK] {label}: does not contain {needle!r}")
    else:
        print(f"[FAIL] {label}: unexpectedly contains {needle!r} in: {text[:300]}")


def extract_id(text, key="ITEM_ID"):
    for line in text.splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return None


async def expect_raises(label, coro, match):
    try:
        await coro
    except ValueError as e:
        if match in str(e):
            print(f"[OK] {label}: ValueError raised with expected text")
            return
        print(f"[FAIL] {label}: ValueError raised but missing {match!r}: {e}")
        return
    except Exception as e:
        print(f"[FAIL] {label}: wrong exception type {type(e).__name__}: {e}")
        return
    print(f"[FAIL] {label}: no exception raised")


async def main():
    ts = int(time.time())
    nb_a = f"mcp_live_test_{ts}_a"
    nb_b = f"mcp_live_test_{ts}_b"
    parent = f"mcp_live_test_{ts}_parent"
    child = f"child_{ts}"  # child notebook name (unique within parent)
    note_title = f"test_note_{ts}"

    print(f"=== Live move test @ {ts} ===")
    print(f"Notebooks: {nb_a}, {nb_b}, {parent}/{child}")

    # 1. Create two flat notebooks
    a_result = await fn(create_notebook)(title=nb_a)
    show("1a. create_notebook A", a_result)
    nb_a_id = extract_id(a_result)
    assert nb_a_id, "could not parse notebook A ID"

    b_result = await fn(create_notebook)(title=nb_b)
    show("1b. create_notebook B", b_result)
    nb_b_id = extract_id(b_result)
    assert nb_b_id, "could not parse notebook B ID"

    # 2. Create a parent notebook and a child inside it
    parent_result = await fn(create_notebook)(title=parent)
    show("2a. create_notebook parent", parent_result)
    parent_id = extract_id(parent_result)

    child_result = await fn(create_notebook)(title=child, parent_id=parent_id)
    show("2b. create_notebook child (inside parent)", child_result)
    child_id = extract_id(child_result)

    # 3. Create a note in notebook A
    note_result = await fn(create_note)(
        title=note_title,
        notebook_name=nb_a,
        body="hello from move live test",
    )
    show("3. create_note in A", note_result)
    note_id = extract_id(note_result)
    assert note_id, "could not parse note ID"

    # 4. Verify it's in A
    listing_a = await fn(find_notes_in_notebook)(notebook_name=nb_a)
    assert_contains("note in A before move", listing_a, note_id)

    # 5. Move the note from A to B via update_note
    move_result = await fn(update_note)(note_id=note_id, notebook_name=nb_b)
    show("5. update_note(notebook_name=B)", move_result)
    assert_contains("move result", move_result, "UPDATE_NOTE")
    assert_contains("move result", move_result, "SUCCESS")

    # 6. Verify the note is now in B, not in A
    listing_a_after = await fn(find_notes_in_notebook)(notebook_name=nb_a)
    assert_not_contains("note NOT in A after move", listing_a_after, note_id)

    listing_b = await fn(find_notes_in_notebook)(notebook_name=nb_b)
    assert_contains("note in B after move", listing_b, note_id)

    # Cross-check via get_note parent_id
    got = await fn(get_note)(note_id=note_id, metadata_only=True)
    assert_contains("get_note shows new parent", got, nb_b_id)

    # 7. Combined update: rename + move to parent/child via path
    new_title = f"{note_title}_renamed"
    combined_result = await fn(update_note)(
        note_id=note_id,
        title=new_title,
        notebook_name=f"{parent}/{child}",
    )
    show("7. update_note(title+notebook_name=path)", combined_result)
    assert_contains("combined update", combined_result, "SUCCESS")

    got2 = await fn(get_note)(note_id=note_id, metadata_only=True)
    assert_contains("new title visible", got2, new_title)
    assert_contains("new parent (child_id)", got2, child_id)

    listing_child = await fn(find_notes_in_notebook)(notebook_name=f"{parent}/{child}")
    assert_contains("note in child notebook", listing_child, note_id)

    # 8. Invalid notebook_name must raise and not mutate
    await expect_raises(
        "invalid notebook_name rejected",
        fn(update_note)(note_id=note_id, notebook_name=f"does_not_exist_{ts}"),
        "not found",
    )
    # Confirm note still in child after failed call
    got3 = await fn(get_note)(note_id=note_id, metadata_only=True)
    assert_contains("note still in child after failed move", got3, child_id)

    # 9. Cleanup: trash the test notebooks (manual purge via Joplin UI if desired)
    for nb_id, label in [
        (nb_a_id, nb_a),
        (nb_b_id, nb_b),
        (parent_id, parent),  # deleting parent trashes child and the note too
    ]:
        try:
            await fn(delete_notebook)(notebook_id=nb_id)
            print(f"[cleanup] trashed notebook {label}")
        except Exception as e:
            print(f"[cleanup] failed to trash {label}: {e}")

    print(f"\nManual cleanup: purge 'mcp_live_test_{ts}_*' from Joplin trash if desired.")


if __name__ == "__main__":
    asyncio.run(main())
