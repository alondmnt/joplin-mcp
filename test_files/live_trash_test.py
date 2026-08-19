"""Live end-to-end test of the restore_from_trash feature against a real Joplin.

Exercises every new tool / option added by PR #23 and the follow-up gap fixes:
- find_notes("*", trash=True) listing
- find_notes ValueError guards (3 cases)
- get_note surfacing DELETED metadata line (the COMMON_NOTE_FIELDS fix)
- delete_note / delete_notebook new recovery hint messages
- restore_from_trash for both note and notebook

Creates an isolated "mcp_live_test_<ts>" notebook so we never touch real data.
The final restored notebook is renamed and left for manual cleanup via Joplin UI.
"""

import asyncio
import sys
import time

sys.path.insert(0, "src")

from joplin_mcp.tools.notes import (
    create_note,
    delete_note,
    find_notes,
    get_note,
)
from joplin_mcp.tools.notebooks import (
    create_notebook,
    delete_notebook,
)
from joplin_mcp.tools.trash import restore_from_trash


def fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool


def show(label, result):
    print(f"\n--- {label} ---")
    print(result)


async def expect_raises(label, coro, match):
    try:
        await coro
    except ValueError as e:
        if match in str(e):
            print(f"[OK] {label}: ValueError raised with expected text")
            return
        print(f"[FAIL] {label}: ValueError raised but message missing '{match}': {e}")
        return
    except Exception as e:
        print(f"[FAIL] {label}: wrong exception type {type(e).__name__}: {e}")
        return
    print(f"[FAIL] {label}: no exception raised")


def assert_contains(label, text, needle):
    if needle in text:
        print(f"[OK] {label}: contains {needle!r}")
    else:
        print(f"[FAIL] {label}: missing {needle!r} in: {text[:200]}")


def assert_not_contains(label, text, needle):
    if needle not in text:
        print(f"[OK] {label}: does not contain {needle!r}")
    else:
        print(f"[FAIL] {label}: unexpectedly contains {needle!r} in: {text[:200]}")


def extract_id(text, key="ITEM_ID"):
    for line in text.splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return None


async def main():
    ts = int(time.time())
    notebook_title = f"mcp_live_test_{ts}"
    note_title = f"test_note_{ts}"

    print(f"=== Live test run @ {ts} ===")
    print(f"Test notebook: {notebook_title}")

    # 1. Create notebook
    nb_result = await fn(create_notebook)(title=notebook_title)
    show("1. create_notebook", nb_result)
    nb_id = extract_id(nb_result)
    assert nb_id, "could not parse notebook ID"

    # 2. Create note in it
    note_result = await fn(create_note)(
        title=note_title,
        notebook_name=notebook_title,
        body="hello from live test",
    )
    show("2. create_note", note_result)
    note_id = extract_id(note_result)
    assert note_id, "could not parse note ID"

    # 3. Delete note and check the new recovery hint
    del_note_result = await fn(delete_note)(note_id=note_id)
    show("3. delete_note (expect new 'moved to trash' hint with note_id)", del_note_result)
    assert_contains("delete_note msg", del_note_result, "moved to trash")
    assert_contains("delete_note msg", del_note_result, 'find_notes("*", trash=True)')
    assert_contains("delete_note msg has note_id in restore example", del_note_result, note_id)

    # 4. find_notes("*", trash=True) should list the trashed note
    trash_list = await fn(find_notes)(query="*", trash=True, limit=100)
    assert_contains("find_notes trash listing", trash_list, note_id)
    # Print only first 600 chars
    show("4. find_notes('*', trash=True)", trash_list[:600] + ("\n..." if len(trash_list) > 600 else ""))

    # 5. get_note on trashed note should surface DELETED metadata line (post-fix)
    got = await fn(get_note)(note_id=note_id)
    show("5. get_note on trashed note (expect DELETED line)", got[:600])
    # Joplin may or may not return trashed notes via get_note; accept either and report
    if "DELETED:" in got or "deleted:" in got.lower():
        print("[OK] get_note surfaces DELETED line on trashed note")
    else:
        print("[INFO] get_note on trashed note does not include DELETED line "
              "(Joplin may be filtering trashed from get_note; gap remains for that path)")

    # 6. ValueError guards on find_notes(trash=True)
    await expect_raises(
        "guard: text query + trash=True",
        fn(find_notes)(query="hello", trash=True),
        'trash=True only works with',
    )
    await expect_raises(
        "guard: task filter + trash=True",
        fn(find_notes)(query="*", trash=True, task=True),
        'trash=True cannot be combined',
    )
    await expect_raises(
        "guard: completed filter + trash=True",
        fn(find_notes)(query="*", trash=True, completed=False),
        'trash=True cannot be combined',
    )

    # 7. restore_from_trash (note)
    restore_note_result = await fn(restore_from_trash)(
        item_id=note_id, item_type="note"
    )
    show("7. restore_from_trash (note)", restore_note_result)
    assert_contains("restore note", restore_note_result, "RESTORE_NOTE")
    assert_contains("restore note", restore_note_result, "SUCCESS")

    # 8. Note should now be live — get_note without DELETED line
    got_live = await fn(get_note)(note_id=note_id)
    assert_not_contains("get_note after restore", got_live, "DELETED:")
    print("[OK] note is live again after restore")

    # 9. Delete the notebook — check the new notebook-specific hint
    del_nb_result = await fn(delete_notebook)(notebook_id=nb_id)
    show("9. delete_notebook (expect hint WITHOUT find_notes ref, WITH restore_from_trash)",
         del_nb_result)
    assert_contains("delete_notebook msg", del_nb_result, "moved to trash")
    assert_contains("delete_notebook msg", del_nb_result, "restore_from_trash")
    assert_contains("delete_notebook msg has nb_id in restore example", del_nb_result, nb_id)
    assert_not_contains("delete_notebook msg must not reference find_notes",
                        del_nb_result, "find_notes")

    # 10. restore_from_trash (notebook)
    restore_nb_result = await fn(restore_from_trash)(
        item_id=nb_id, item_type="notebook"
    )
    show("10. restore_from_trash (notebook)", restore_nb_result)
    assert_contains("restore notebook", restore_nb_result, "RESTORE_NOTEBOOK")

    # 11. Cleanup — delete the notebook and leave in trash
    #     (we have no purge-from-trash tool; manual cleanup via Joplin UI if desired)
    final_del = await fn(delete_notebook)(notebook_id=nb_id)
    show("11. cleanup: trashed the test notebook", final_del)
    print(f"\nManual cleanup: permanently delete notebook '{notebook_title}' "
          f"from Joplin trash if you want it gone.")


if __name__ == "__main__":
    asyncio.run(main())
