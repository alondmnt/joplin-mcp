#!/usr/bin/env python3
"""Development install entry point.

Invoked by ``install.sh`` / ``install.bat`` after they run ``pip install -e .``
from a cloned repo. Delegates to the canonical runner in
``src/joplin_mcp/install.py`` with ``is_development=True`` so the config
lands inside the repo rather than the user's home directory.

Pip-installed users do not run this file -- they get the ``joplin-mcp-install``
console script (or ``python -m joplin_mcp.install``), which calls the same
``main()`` with ``is_development=False``.
"""

import sys

from joplin_mcp.install import main

if __name__ == "__main__":
    sys.exit(main(is_development=True))
