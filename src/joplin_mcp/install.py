#!/usr/bin/env python3
"""Module-level installation script for joplin-mcp package.

This can be run as: python -m joplin_mcp.install
"""

import sys
import os
from pathlib import Path

# Add the root install script to the path and import it
def main():
    """Main entry point for module-level install."""
    # Try to import the main install script
    try:
        # Look for install.py in the current directory first
        current_dir = Path.cwd()
        install_script = current_dir / "install.py"
        
        if install_script.exists():
            # We're in the development directory, use the local install.py
            sys.path.insert(0, str(current_dir))
            import install
            return install.main()
        else:
            # We're in a pip-installed package, use the embedded install logic
            from .install_embedded import main as embedded_main
            return embedded_main()
            
    except ImportError:
        print("❌ Installation script not found.")
        print("ℹ️  Please run from the joplin-mcp directory or ensure the package is properly installed.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 