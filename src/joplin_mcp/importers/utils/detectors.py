"""Detector helpers for importer heuristics."""

import re
from pathlib import Path


def looks_like_raw_export(path: Path) -> bool:
    """Heuristically determine if a directory is a Joplin RAW export.

    Criteria:
    - Prefer the presence of a root-level 'resources' directory AND at least
      one Markdown file somewhere under this directory.
    - As a secondary signal (when resources/ is missing), look for Joplin's
      KV-style metadata blocks in top-level markdown files (id: <32 hex>, type_: <digit>).

    This is intentionally conservative for nested detection: only the directory
    being tested is considered a RAW root; we don't scan ancestor/descendant
    relationships here. Callers decide which directories to test.
    """
    try:
        res_dir = path / "resources"
        if res_dir.exists() and res_dir.is_dir():
            try:
                # Any markdown anywhere under this directory
                if any(path.rglob("*.md")):
                    return True
            except Exception:
                pass
    except Exception:
        pass

    # Lightweight KV metadata check for top-level markdown only
    try:
        md_top = list(path.glob("*.md"))
        if md_top:
            def looks_like_joplin_kv(md_path: Path) -> bool:
                try:
                    text = md_path.read_text(encoding="utf-8", errors="ignore")
                    tail = "\n".join(text.strip().splitlines()[-40:])
                    has_id = re.search(r"^id:\s*[a-f0-9]{32}$", tail, re.M) is not None
                    has_type = re.search(r"^type_:\s*\d+", tail, re.M) is not None
                    return has_id and has_type
                except Exception:
                    return False

            sample = md_top[: min(10, len(md_top))]
            matches = sum(1 for f in sample if looks_like_joplin_kv(f))
            if matches >= 2:
                return True
    except Exception:
        pass

    return False

