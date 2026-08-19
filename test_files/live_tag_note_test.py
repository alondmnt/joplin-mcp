"""Live end-to-end test of tag_note / untag_note list support (#22).

Exercises:
- tag_note scalar + scalar (backwards-compatible output)
- tag_note list notes + list tags (cartesian)
- untag_note list notes + list tags (cartesian)
- missing tag in list raises ValueError before any mutation
- partial-failure report when one note_id is bogus

Creates an isolated "mcp_live_test_<ts>" notebook and two test tags. Trashes
notebook + tags at the end; manual purge via Joplin UI if desired.
"""

import asyncio
import sys
import time

sys.path.insert(0, "src")

from joplin_mcp.tools.notes import create_note
from joplin_mcp.tools.notebooks import create_notebook, delete_notebook
from joplin_mcp.tools.tags import (
    create_tag,
    delete_tag,
    get_tags_by_note,
    tag_note,
    untag_note,
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
    nb_title = f"mcp_live_test_{ts}"
    tag_a = f"tag_a_{ts}"
    tag_b = f"tag_b_{ts}"

    print(f"=== Live tag-list test @ {ts} ===")

    # 1. Setup: notebook + two notes + two tags
    nb_result = await fn(create_notebook)(title=nb_title)
    show("1a. create_notebook", nb_result)
    nb_id = extract_id(nb_result)

    n1 = extract_id(await fn(create_note)(title=f"note1_{ts}", notebook_name=nb_title, body="n1"))
    n2 = extract_id(await fn(create_note)(title=f"note2_{ts}", notebook_name=nb_title, body="n2"))
    n3 = extract_id(await fn(create_note)(title=f"note3_{ts}", notebook_name=nb_title, body="n3"))
    print(f"notes created: {n1}, {n2}, {n3}")

    tag_a_id = extract_id(await fn(create_tag)(title=tag_a))
    tag_b_id = extract_id(await fn(create_tag)(title=tag_b))
    print(f"tags created: {tag_a} ({tag_a_id}), {tag_b} ({tag_b_id})")

    # 2. Scalar + scalar on a dedicated note (n3) for backwards-compat check
    scalar_result = await fn(tag_note)(note_id=n3, tag_name=tag_a)
    show("2. tag_note scalar+scalar (expect single-op format)", scalar_result)
    assert_contains("scalar format", scalar_result, "OPERATION: TAGGED_NOTE")
    assert_contains("scalar format", scalar_result, "STATUS: SUCCESS")
    assert_not_contains("scalar format not aggregated", scalar_result, "TOTAL_OPS")

    # 3. List x list cartesian tagging on fresh notes (n1, n2) — no overlap with step 2
    bulk_tag_result = await fn(tag_note)(note_id=[n1, n2], tag_name=[tag_a, tag_b])
    show("3. tag_note list x list (expect TOTAL_OPS=4)", bulk_tag_result)
    assert_contains("bulk tag", bulk_tag_result, "OPERATION: TAG_NOTE")
    assert_contains("bulk tag", bulk_tag_result, "TOTAL_OPS: 4")
    assert_contains("bulk tag", bulk_tag_result, "SUCCEEDED: 4")
    assert_contains("bulk tag", bulk_tag_result, "STATUS: SUCCESS")

    # Verify each note has both tags via get_tags_by_note
    n1_tags = await fn(get_tags_by_note)(note_id=n1)
    assert_contains("n1 has tag_a", n1_tags, tag_a)
    assert_contains("n1 has tag_b", n1_tags, tag_b)
    n2_tags = await fn(get_tags_by_note)(note_id=n2)
    assert_contains("n2 has tag_a", n2_tags, tag_a)
    assert_contains("n2 has tag_b", n2_tags, tag_b)

    # 4. Missing-tag guard: raise before any delete
    await expect_raises(
        "missing tag raises pre-mutation",
        fn(tag_note)(note_id=[n1], tag_name=[tag_a, f"ghost_{ts}"]),
        "not found",
    )

    # 5. Partial-failure report: mix a valid fresh pair with a bogus note ID.
    #    After step 3, n1/n2 already have tag_a, so we untag tag_a from n1 first
    #    to give this step a clean success + clean failure.
    await fn(untag_note)(note_id=n1, tag_name=tag_a)
    bogus = "f" * 32
    partial = await fn(tag_note)(note_id=[n1, bogus], tag_name=[tag_a])
    show("5. tag_note partial failure (expect PARTIAL, 1 success + 1 failure)", partial)
    assert_contains("partial status", partial, "STATUS: PARTIAL")
    assert_contains("partial succeeded", partial, "SUCCEEDED: 1")
    assert_contains("partial failed", partial, "FAILED: 1")
    assert_contains("partial failures heading", partial, "FAILURES:")
    assert_contains("bogus id in failure", partial, bogus)

    # 6. List x list cartesian untag
    bulk_untag_result = await fn(untag_note)(note_id=[n1, n2], tag_name=[tag_a, tag_b])
    show("6. untag_note list x list (expect TOTAL_OPS=4)", bulk_untag_result)
    assert_contains("bulk untag", bulk_untag_result, "OPERATION: UNTAG_NOTE")
    assert_contains("bulk untag", bulk_untag_result, "TOTAL_OPS: 4")
    assert_contains("bulk untag", bulk_untag_result, "SUCCEEDED: 4")

    # Verify tags removed
    n1_tags_after = await fn(get_tags_by_note)(note_id=n1)
    assert_not_contains("n1 tag_a removed", n1_tags_after, tag_a)
    assert_not_contains("n1 tag_b removed", n1_tags_after, tag_b)
    n2_tags_after = await fn(get_tags_by_note)(note_id=n2)
    assert_not_contains("n2 tag_a removed", n2_tags_after, tag_a)
    assert_not_contains("n2 tag_b removed", n2_tags_after, tag_b)

    # 7. Cleanup
    try:
        await fn(delete_notebook)(notebook_id=nb_id)
        print(f"[cleanup] trashed notebook {nb_title}")
    except Exception as e:
        print(f"[cleanup] notebook trash failed: {e}")
    for tid, tname in [(tag_a_id, tag_a), (tag_b_id, tag_b)]:
        try:
            await fn(delete_tag)(tag_id=tid)
            print(f"[cleanup] deleted tag {tname}")
        except Exception as e:
            print(f"[cleanup] tag delete failed ({tname}): {e}")


if __name__ == "__main__":
    asyncio.run(main())
