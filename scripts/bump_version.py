#!/usr/bin/env python3
"""Bump (or verify) the project version across every file that hard-codes it.

The version lives in four places that must agree, or a release ships
inconsistent metadata:

- ``pyproject.toml``        -> ``version`` (the PyPI build reads this)
- ``src/joplin_mcp/__init__.py`` -> ``__version__``
- ``server.json``          -> top-level ``version`` AND ``packages[*].version``
  (the MCP registry publish reads server.json as committed)

This script is the single owner of that list. Use it two ways:

    python scripts/bump_version.py 0.9.0      # rewrite all locations
    python scripts/bump_version.py --check 0.9.0   # verify; exit 1 on mismatch

``--check`` is what CI runs against the release tag, so a forgotten or
partial bump fails the release loudly instead of being silently rewritten
at publish time (which is how server.json drifted in the first place).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PYPROJECT = REPO_ROOT / "pyproject.toml"
INIT = REPO_ROOT / "src" / "joplin_mcp" / "__init__.py"
SERVER_JSON = REPO_ROOT / "server.json"

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-.+][0-9A-Za-z.-]+)?$")
# A line that is exactly `version = "X"` — not target-version/python_version/etc.
PYPROJECT_RE = re.compile(r'^version = "([^"]+)"', re.MULTILINE)
INIT_RE = re.compile(r'^__version__ = "([^"]+)"', re.MULTILINE)


def read_versions() -> dict[str, list[str]]:
    """Return the current version string(s) found in each location.

    server.json contributes several values (top-level plus one per package);
    they are returned as a list so a partial mismatch is visible.
    """
    pyproject_match = PYPROJECT_RE.search(PYPROJECT.read_text())
    init_match = INIT_RE.search(INIT.read_text())
    server = json.loads(SERVER_JSON.read_text())

    return {
        "pyproject.toml": [pyproject_match.group(1)] if pyproject_match else [],
        "src/joplin_mcp/__init__.py": [init_match.group(1)] if init_match else [],
        "server.json": [server["version"]]
        + [pkg["version"] for pkg in server.get("packages", [])],
    }


def check(version: str) -> int:
    """Report any location whose version differs from ``version``.

    Returns a process exit code: 0 if every location agrees, 1 otherwise.
    """
    found = read_versions()
    mismatched = {
        loc: values
        for loc, values in found.items()
        if any(v != version for v in values) or not values
    }
    for loc, values in found.items():
        print(f"  {loc}: {', '.join(values) or '(version not found)'}")
    if mismatched:
        print(f"\nversion mismatch: expected {version} everywhere", file=sys.stderr)
        return 1
    print(f"\nall locations at {version}")
    return 0


def bump(version: str) -> None:
    """Rewrite every location to ``version``, reporting each change."""
    pyproject_text, n = PYPROJECT_RE.subn(f'version = "{version}"', PYPROJECT.read_text())
    if n != 1:
        raise SystemExit(f"expected exactly one version line in pyproject.toml, found {n}")
    PYPROJECT.write_text(pyproject_text)

    init_text, n = INIT_RE.subn(f'__version__ = "{version}"', INIT.read_text())
    if n != 1:
        raise SystemExit(f"expected exactly one __version__ in __init__.py, found {n}")
    INIT.write_text(init_text)

    server = json.loads(SERVER_JSON.read_text())
    server["version"] = version
    for pkg in server.get("packages", []):
        pkg["version"] = version
    # Match the file's existing 2-space indent and trailing newline.
    SERVER_JSON.write_text(json.dumps(server, indent=2) + "\n")

    print(f"bumped all locations to {version}")
    for loc, values in read_versions().items():
        print(f"  {loc}: {', '.join(values)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="target version, e.g. 0.9.0")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify all locations equal VERSION and exit non-zero on mismatch, "
        "instead of rewriting them (used by the release workflow)",
    )
    args = parser.parse_args(argv)

    if not VERSION_RE.match(args.version):
        parser.error(f"not a valid version string: {args.version!r}")

    if args.check:
        return check(args.version)
    bump(args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
