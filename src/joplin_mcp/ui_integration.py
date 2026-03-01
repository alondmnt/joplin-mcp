#!/usr/bin/env python3
"""UI Integration module for joplin-mcp.

This module provides:
1. Interactive configuration logic (permissions, tokens)
2. Chat interface integration (Claude Desktop, Ollama, etc.)
3. Installation orchestration helpers

Designed to be extensible for future chat interfaces.
"""

import json
import os
import shutil
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

# Import defaults from config module
from .config import JoplinMCPConfig


# Color codes for terminal output
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def print_colored(message: str, color: str = Colors.WHITE) -> None:
    """Print a colored message."""
    print(f"{color}{message}{Colors.END}")


def print_step(step: str) -> None:
    """Print a formatted step."""
    print_colored(f"\n🔧 {step}", Colors.BLUE + Colors.BOLD)


def print_success(message: str) -> None:
    """Print a success message."""
    print_colored(f"✅ {message}", Colors.GREEN)


def print_error(message: str) -> None:
    """Print an error message."""
    print_colored(f"❌ {message}", Colors.RED)


def print_warning(message: str) -> None:
    """Print a warning message."""
    print_colored(f"⚠️  {message}", Colors.YELLOW)


def print_info(message: str) -> None:
    """Print an info message."""
    print_colored(f"ℹ️  {message}", Colors.BLUE)


# === INTERACTIVE INPUT FUNCTIONS ===


def get_token_interactively() -> str:
    """Prompt user for Joplin API token with guidance."""
    print_step("Joplin API Token Configuration")
    print_info(
        "To use the Joplin MCP server, you need to provide your Joplin API token."
    )
    print_info(
        "You can find this in Joplin: Tools > Options > Web Clipper > Authorization token"
    )
    print()

    # Check if token is already set in environment
    existing_token = os.environ.get("JOPLIN_TOKEN")
    if existing_token:
        print_info(f"Found existing token in environment: {existing_token[:10]}...")
        use_existing = input("Use existing token? (y/n): ").lower().strip()
        if use_existing in ("y", "yes", ""):
            return existing_token

    while True:
        token = input("Enter your Joplin API token: ").strip()
        if token:
            if len(token) < 10:
                print_warning("Token seems too short. Please double-check.")
                continue
            return token
        else:
            print_warning("Token is required. Please enter a valid token.")


def get_permission_settings() -> Dict[str, bool]:
    """Get permission settings from user with three levels of control."""
    print_step("Tool Permission Configuration")
    print_info("Configure which operations the AI assistant can perform:")
    print_info("You can control access at three levels for security and safety.")
    print()

    # Define tool categories
    write_tools = ["create_note", "create_notebook", "create_tag", "import_from_file"]

    update_tools = [
        "update_note",
        "edit_note",
        "update_notebook",
        "update_tag",
        "tag_note",
        "untag_note",
    ]

    delete_tools = ["delete_note", "delete_notebook", "delete_tag"]

    # Get user preferences
    permissions = {}

    # 1. Write Permission
    print_colored(
        "1. 📝 WRITE PERMISSION (Creating new objects)", Colors.BLUE + Colors.BOLD
    )
    print_info("   Tools included:")
    for tool in write_tools:
        print_info(f"   • {tool}")
    print()

    while True:
        write_perm = (
            input("Allow creating new notes, notebooks, and tags? (y/n) [default: y]: ")
            .lower()
            .strip()
        )
        if write_perm in ("y", "yes", ""):
            write_enabled = True
            break
        elif write_perm in ("n", "no"):
            write_enabled = False
            break
        else:
            print_warning("Please enter 'y' for yes or 'n' for no.")

    for tool in write_tools:
        permissions[tool] = write_enabled

    # 2. Update Permission
    print()
    print_colored(
        "2. ✏️  UPDATE PERMISSION (Modifying existing objects)",
        Colors.YELLOW + Colors.BOLD,
    )
    print_info("   Tools included:")
    for tool in update_tools:
        print_info(f"   • {tool}")
    print()

    while True:
        update_perm = (
            input(
                "Allow updating existing notes, notebooks, tags, and relationships? (y/n) [default: y]: "
            )
            .lower()
            .strip()
        )
        if update_perm in ("y", "yes", ""):
            update_enabled = True
            break
        elif update_perm in ("n", "no"):
            update_enabled = False
            break
        else:
            print_warning("Please enter 'y' for yes or 'n' for no.")

    for tool in update_tools:
        permissions[tool] = update_enabled

    # 3. Delete Permission
    print()
    print_colored(
        "3. 🗑️  DELETE PERMISSION (Permanently removing objects)",
        Colors.RED + Colors.BOLD,
    )
    print_info("   Tools included:")
    for tool in delete_tools:
        print_info(f"   • {tool}")
    print()
    print_warning("⚠️  These operations are DESTRUCTIVE and cannot be undone!")

    while True:
        delete_perm = (
            input("Allow deleting notes, notebooks, and tags? (y/n) [default: n]: ")
            .lower()
            .strip()
        )
        if delete_perm in ("y", "yes"):
            delete_enabled = True
            break
        elif delete_perm in ("n", "no", ""):
            delete_enabled = False
            break
        else:
            print_warning("Please enter 'y' for yes or 'n' for no.")

    for tool in delete_tools:
        permissions[tool] = delete_enabled

    # Summary
    print()
    print_colored("📋 Permission Summary:", Colors.BOLD)
    print_info(
        f"• Write (create new): {'✅ Enabled' if write_enabled else '❌ Disabled'}"
    )
    print_info(
        f"• Update (modify existing): {'✅ Enabled' if update_enabled else '❌ Disabled'}"
    )
    print_info(
        f"• Delete (remove permanently): {'✅ Enabled' if delete_enabled else '❌ Disabled'}"
    )

    return permissions


def get_content_privacy_settings() -> Dict[str, Union[str, int]]:
    """Get content privacy settings from user with three context levels."""
    print_step("Content Privacy Configuration")
    print_info("Configure what note content the AI assistant can see:")
    print_info(
        "This is important for privacy and security when dealing with sensitive notes."
    )
    print()

    print_colored("📋 Content Exposure Levels:", Colors.BOLD)
    print_info("• none:    Only titles and metadata (maximum privacy)")
    print_info("• preview: Short content snippets (balanced privacy)")
    print_info("• full:    Complete note content (full functionality)")
    print()

    content_exposure = {}

    # 1. Search Results
    print_colored("1. 🔍 SEARCH RESULTS", Colors.BLUE + Colors.BOLD)
    print_info("   When searching notes, what content should be visible?")
    print_info(
        "   Contexts: find_notes, find_notes_with_tag, find_notes_in_notebook, get_all_notes"
    )
    print()

    while True:
        default_search = JoplinMCPConfig.DEFAULT_CONTENT_EXPOSURE["search_results"]
        search_level = (
            input(
                f"Search results content level (none/preview/full) [default: {default_search}]: "
            )
            .lower()
            .strip()
        )
        if search_level in ("", default_search):
            content_exposure["search_results"] = default_search
            break
        elif search_level in ("none", "preview", "full"):
            content_exposure["search_results"] = search_level
            break
        else:
            print_warning("Please enter 'none', 'preview', or 'full'.")

    # 2. Individual Notes
    print()
    print_colored("2. 📝 INDIVIDUAL NOTES", Colors.YELLOW + Colors.BOLD)
    print_info("   When retrieving a specific note, what content should be visible?")
    print_info("   Contexts: get_note operation")
    print()

    while True:
        default_notes = JoplinMCPConfig.DEFAULT_CONTENT_EXPOSURE["individual_notes"]
        note_level = (
            input(
                f"Individual note content level (none/preview/full) [default: {default_notes}]: "
            )
            .lower()
            .strip()
        )
        if note_level in ("", default_notes):
            content_exposure["individual_notes"] = default_notes
            break
        elif note_level in ("none", "preview", "full"):
            content_exposure["individual_notes"] = note_level
            break
        else:
            print_warning("Please enter 'none', 'preview', or 'full'.")

    # 3. Note Listings
    print()
    print_colored("3. 📂 NOTE LISTINGS", Colors.MAGENTA + Colors.BOLD)
    print_info("   When listing notes by notebook/tag, what content should be visible?")
    print_info("   Contexts: find_notes_in_notebook, find_notes_with_tag")
    print()

    while True:
        default_listings = JoplinMCPConfig.DEFAULT_CONTENT_EXPOSURE["listings"]
        listing_level = (
            input(
                f"Note listings content level (none/preview/full) [default: {default_listings}]: "
            )
            .lower()
            .strip()
        )
        if listing_level in ("", default_listings):
            content_exposure["listings"] = default_listings
            break
        elif listing_level in ("none", "preview", "full"):
            content_exposure["listings"] = listing_level
            break
        else:
            print_warning("Please enter 'none', 'preview', or 'full'.")

    # 4. Preview Length (if any previews are enabled)
    if any(level == "preview" for level in content_exposure.values()):
        print()
        print_colored("4. ✂️  PREVIEW LENGTH", Colors.CYAN + Colors.BOLD)
        print_info("   Maximum length for content previews (in characters)")
        print()

        while True:
            try:
                default_length = JoplinMCPConfig.DEFAULT_CONTENT_EXPOSURE[
                    "max_preview_length"
                ]
                length_input = input(
                    f"Preview length (50-500) [default: {default_length}]: "
                ).strip()
                if length_input == "":
                    content_exposure["max_preview_length"] = default_length
                    break
                length = int(length_input)
                if 50 <= length <= 500:
                    content_exposure["max_preview_length"] = length
                    break
                else:
                    print_warning(
                        "Preview length must be between 50 and 500 characters."
                    )
            except ValueError:
                print_warning("Please enter a valid number.")
    else:
        content_exposure["max_preview_length"] = (
            JoplinMCPConfig.DEFAULT_CONTENT_EXPOSURE["max_preview_length"]
        )

    # Summary
    print()
    print_colored("🔒 Privacy Summary:", Colors.BOLD)
    print_info(f"• Search results: {content_exposure['search_results']}")
    print_info(f"• Individual notes: {content_exposure['individual_notes']}")
    print_info(f"• Note listings: {content_exposure['listings']}")
    print_info(f"• Preview length: {content_exposure['max_preview_length']} characters")

    # Privacy assessment
    privacy_score = 0
    for context in ["search_results", "individual_notes", "listings"]:
        level = content_exposure[context]
        if level == "none":
            privacy_score += 2
        elif level == "preview":
            privacy_score += 1
        # "full" adds 0

    print()
    if privacy_score >= 5:
        print_colored(
            "✅ High Privacy: Minimal content exposure", Colors.GREEN + Colors.BOLD
        )
    elif privacy_score >= 3:
        print_colored(
            "⚠️  Balanced Privacy: Some content visible", Colors.YELLOW + Colors.BOLD
        )
    else:
        print_colored(
            "❌ Low Privacy: Significant content exposure", Colors.RED + Colors.BOLD
        )
        print_warning(
            "Consider using 'none' or 'preview' for better privacy protection."
        )

    return content_exposure


# === CHAT INTERFACE INTEGRATION ===


class ChatInterface(ABC):
    """Abstract base class for chat interface integrations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the chat interface."""
        pass

    @abstractmethod
    def find_config_file(self) -> Optional[Path]:
        """Find the configuration file for this chat interface."""
        pass

    def create_base_mcp_config(
        self, config_path: Path, is_development: bool = False
    ) -> Dict[str, Any]:
        """Create base MCP server configuration that works for most interfaces."""
        python_path = (
            shutil.which("python") or shutil.which("python3") or sys.executable
        )

        if is_development:
            # Development install - run the module directly and set PYTHONPATH to src
            project_root = config_path.parent
            src_path = project_root / "src"

            mcp_config = {
                "command": python_path,
                "args": ["-m", "joplin_mcp.server", "--config", str(config_path)],
                "cwd": str(project_root),
                "env": {"PYTHONPATH": str(src_path)},
            }
        else:
            # Pip install - use module command
            mcp_config = {"command": "joplin-mcp-server", "env": {}}

        # Add Joplin-specific environment variables
        env_vars = self.get_joplin_environment_variables(config_path)
        mcp_config["env"].update(env_vars)

        return mcp_config

    def get_joplin_environment_variables(self, config_path: Path) -> Dict[str, str]:
        """Extract Joplin environment variables from config file.

        Standardizes on JOPLIN_TOKEN, JOPLIN_HOST, JOPLIN_PORT, JOPLIN_VERIFY_SSL.
        Also sets JOPLIN_URL for maximum compatibility where supported.
        """
        env_vars = {}

        if not config_path.exists():
            return env_vars

        try:
            # Preferred path using typed config loader
            from .config import JoplinMCPConfig

            cfg = JoplinMCPConfig.from_file(config_path)

            if cfg.token:
                env_vars["JOPLIN_TOKEN"] = cfg.token
            # Provide both URL and discrete host/port for consumers
            env_vars["JOPLIN_HOST"] = str(cfg.host)
            env_vars["JOPLIN_PORT"] = str(cfg.port)
            if not cfg.verify_ssl:
                env_vars["JOPLIN_VERIFY_SSL"] = "false"
            # Optional convenience var used by some fallbacks
            env_vars["JOPLIN_URL"] = cfg.base_url

        except Exception:
            # Fallback to raw JSON reading
            try:
                with open(config_path) as f:
                    raw = json.load(f)
                token = raw.get("token")
                if token:
                    env_vars["JOPLIN_TOKEN"] = token
                host = raw.get("host")
                port = raw.get("port")
                if host is not None:
                    env_vars["JOPLIN_HOST"] = str(host)
                if port is not None:
                    env_vars["JOPLIN_PORT"] = str(port)
                if raw.get("verify_ssl") is False:
                    env_vars["JOPLIN_VERIFY_SSL"] = "false"
            except (json.JSONDecodeError, FileNotFoundError):
                pass

        return env_vars

    def create_mcp_config(
        self, config_path: Path, is_development: bool = False
    ) -> Dict[str, Any]:
        """Create MCP server configuration for this interface.

        Default implementation works for most interfaces.
        Override if you need custom configuration structure.
        """
        return self.create_base_mcp_config(config_path, is_development)

    @abstractmethod
    def get_manual_config_instructions(
        self, config_path: Path, is_development: bool = False
    ) -> str:
        """Get manual configuration instructions for this interface."""
        pass


class ClaudeDesktopInterface(ChatInterface):
    """Claude Desktop integration."""

    @property
    def name(self) -> str:
        return "Claude Desktop"

    def find_config_file(self) -> Optional[Path]:
        """Find Claude Desktop configuration file."""
        possible_paths = [
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json",  # macOS
            Path.home()
            / ".config"
            / "claude-desktop"
            / "claude_desktop_config.json",  # Linux
            Path.home()
            / "AppData"
            / "Roaming"
            / "Claude"
            / "claude_desktop_config.json",  # Windows
        ]

        for path in possible_paths:
            if path.exists():
                return path

        return None

    # Claude Desktop uses the default base implementation

    def get_manual_config_instructions(
        self, config_path: Path, is_development: bool = False
    ) -> str:
        """Get manual configuration instructions for Claude Desktop."""
        mcp_config = self.create_mcp_config(config_path, is_development)

        full_config = {"mcpServers": {"joplin": mcp_config}}

        config_locations = [
            "**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`",
            "**Linux:** `~/.config/claude-desktop/claude_desktop_config.json`",
            "**Windows:** `%APPDATA%\\Claude\\claude_desktop_config.json`",
        ]

        return f"""Add this to your Claude Desktop configuration file:

{chr(10).join(config_locations)}

```json
{json.dumps(full_config, indent=2)}
```"""


class OllamaInterface(ChatInterface):
    """Ollama integration (future implementation)."""

    @property
    def name(self) -> str:
        return "Ollama"

    def find_config_file(self) -> Optional[Path]:
        """Find Ollama configuration file."""
        # TODO: Implement when Ollama MCP support is added
        return None

    # Ollama uses the default base implementation
    # Override get_joplin_environment_variables() if Ollama needs different env vars

    def get_manual_config_instructions(
        self, config_path: Path, is_development: bool = False
    ) -> str:
        """Get manual configuration instructions for Ollama."""
        return "Ollama MCP integration coming soon!"


class JanInterface(ChatInterface):
    """Jan AI integration."""

    @property
    def name(self) -> str:
        return "Jan AI"

    def find_config_file(self) -> Optional[Path]:
        """Find Jan AI configuration file."""
        possible_paths = [
            Path.home()
            / "Library"
            / "Application Support"
            / "Jan"
            / "data"
            / "mcp_config.json",  # macOS (confirmed)
            Path.home()
            / "AppData"
            / "Roaming"
            / "Jan"
            / "data"
            / "mcp_config.json",  # Windows (likely)
            Path.home()
            / "AppData"
            / "Local"
            / "Jan"
            / "data"
            / "mcp_config.json",  # Windows Alternative
            Path.home() / ".config" / "jan" / "data" / "mcp_config.json",  # Linux XDG
            Path.home() / ".jan" / "data" / "mcp_config.json",  # Linux Alternative
        ]

        for path in possible_paths:
            if path.exists():
                return path

        return None

    # Jan AI uses the default base implementation

    def get_manual_config_instructions(
        self, config_path: Path, is_development: bool = False
    ) -> str:
        """Get manual configuration instructions for Jan AI."""
        mcp_config = self.create_mcp_config(config_path, is_development)

        # Jan AI uses the same format as Claude Desktop, with an optional "active" field
        full_config = {
            "mcpServers": {
                "joplin": {
                    **mcp_config,
                    "active": True,  # Enable the MCP server by default
                }
            }
        }

        config_locations = [
            "**macOS:** `~/Library/Application Support/Jan/data/mcp_config.json`",
            "**Windows:** `%APPDATA%\\Jan\\data\\mcp_config.json` (likely)",
            "**Linux:** `~/.config/jan/data/mcp_config.json` (likely)",
        ]

        return f"""Add this to your Jan AI MCP configuration file:

{chr(10).join(config_locations)}

```json
{json.dumps(full_config, indent=2)}
```

**Important Notes:**
1. The `"active": true` field enables the MCP server in Jan AI
2. Create the `mcp_config.json` file if it doesn't exist
3. Restart Jan AI after making configuration changes
4. Make sure Joplin is running and Web Clipper is enabled

If you have trouble:
- Check Jan AI's GitHub repository: https://github.com/janhq/jan
- Verify the file path exists (create directories if needed)
- Check Jan AI's logs for MCP connection errors"""


# === CHAT INTERFACE REGISTRY ===

_INTERFACES: Dict[str, Type[ChatInterface]] = {
    "claude": ClaudeDesktopInterface,
    "ollama": OllamaInterface,
    "jan": JanInterface,
}


def get_available_interfaces() -> List[str]:
    """Get list of available chat interface names."""
    return list(_INTERFACES.keys())


def get_interface(name: str) -> ChatInterface:
    """Get a chat interface instance by name."""
    if name not in _INTERFACES:
        raise ValueError(
            f"Unknown interface: {name}. Available: {list(_INTERFACES.keys())}"
        )

    return _INTERFACES[name]()


def register_interface(name: str, interface_class: Type[ChatInterface]) -> None:
    """Register a new chat interface."""
    _INTERFACES[name] = interface_class


# === INSTALLATION ORCHESTRATION ===


def update_chat_interface_config(
    interface_name: str, config_path: Path, is_development: bool = False
) -> bool:
    """Update a chat interface configuration with the MCP server.

    Args:
        interface_name: Name of the chat interface (e.g., 'claude', 'ollama')
        config_path: Path to the joplin-mcp configuration file
        is_development: Whether this is a development install

    Returns:
        True if configuration was updated successfully, False otherwise
    """
    print_step(f"Configuring {interface_name.title()}")

    try:
        interface = get_interface(interface_name)
    except ValueError as e:
        print_error(str(e))
        return False

    # Find the interface's config file
    interface_config_path = interface.find_config_file()
    if not interface_config_path:
        print_warning(f"Could not find {interface.name} configuration file.")
        print_info("You'll need to manually add the MCP server configuration.")
        print()
        print_info("Manual configuration:")
        print_colored(
            interface.get_manual_config_instructions(config_path, is_development),
            Colors.CYAN,
        )
        return False

    print_info(f"Found {interface.name} config at: {interface_config_path}")

    # Load existing config
    interface_config = {}
    if interface_config_path.exists():
        try:
            with open(interface_config_path) as f:
                interface_config = json.load(f)
        except json.JSONDecodeError:
            print_warning(f"{interface.name} config is invalid. Creating new one.")

    # Ensure mcpServers section exists for interfaces that use this format
    if interface_name in ["claude", "jan"]:
        if "mcpServers" not in interface_config:
            interface_config["mcpServers"] = {}

        # Add Joplin MCP server config
        mcp_config = interface.create_mcp_config(config_path, is_development)

        # Jan AI requires an "active" field to enable the MCP server
        if interface_name == "jan":
            mcp_config["active"] = True

        interface_config["mcpServers"]["joplin"] = mcp_config
    else:
        # For other interfaces, we might need different configuration formats
        print_warning(
            f"Auto-configuration for {interface.name} is not yet implemented."
        )
        print_info("Falling back to manual configuration instructions.")
        return False

    # Backup existing config
    backup_path = interface_config_path.with_suffix(".json.backup")
    if interface_config_path.exists():
        shutil.copy2(interface_config_path, backup_path)
        print_info(f"Backed up existing config to {backup_path}")

    # Save updated config
    with open(interface_config_path, "w") as f:
        json.dump(interface_config, f, indent=2)

    print_success(f"Updated {interface.name} configuration at {interface_config_path}")
    return True


def test_joplin_connection(config_path: Path) -> bool:
    """Test connection to Joplin using the configured settings."""
    print_step("Testing Joplin Connection")

    try:
        from .config import JoplinMCPConfig

        # Load config and test connection
        config = JoplinMCPConfig.from_file(config_path)
        if config.test_connection():
            print_success("Successfully connected to Joplin!")
            return True
        else:
            print_error("Failed to connect to Joplin.")
            return False
    except ImportError:
        print_warning("Could not import Joplin MCP modules.")
        print_info("Make sure to install dependencies: pip install -r requirements.txt")
        return False
    except Exception as e:
        print_error(f"Connection test failed: {e}")
        return False


def print_header(title: str) -> None:
    """Print a formatted header."""
    print_colored("\n" + "=" * 60, Colors.CYAN)
    print_colored(f"  {title}", Colors.CYAN + Colors.BOLD)
    print_colored("=" * 60, Colors.CYAN)


def print_final_instructions(
    config_path: Path, interface_results: Dict[str, bool], is_development: bool = False
):
    """Print final setup instructions with install-specific details."""
    print_header("Installation Complete!")

    print_success("Joplin MCP Server has been configured successfully!")
    print()

    print_colored("📋 What was configured:", Colors.BOLD)
    print_info(f"• Joplin configuration: {config_path}")

    # Show results for each interface that was attempted
    for interface_name, success in interface_results.items():
        interface = get_interface(interface_name)
        if success:
            print_info(f"• {interface.name} configuration updated")
        else:
            print_warning(f"• {interface.name} configuration needs manual setup")

    print()
    print_colored("🚀 Next steps:", Colors.BOLD)

    # Show manual instructions for any failed configurations
    any_failed = any(not success for success in interface_results.values())
    if any_failed:
        for interface_name, success in interface_results.items():
            if not success:
                interface = get_interface(interface_name)
                print_info(
                    f"Manually add the MCP server to your {interface.name} config:"
                )
                print_colored(
                    interface.get_manual_config_instructions(
                        config_path, is_development
                    ),
                    Colors.CYAN,
                )
                print()

    # Show install-specific information
    if not is_development:
        print()
        print_colored("📝 Running from pip install:", Colors.BOLD)
        print_info("• Server command: joplin-mcp-server")
        print_info("• Install command: joplin-mcp-install")
        print_info("• Module command: python -m joplin_mcp.install")

    print()
    print_colored("🔧 Available tools:", Colors.BOLD)

    # Load the actual configuration to show only enabled tools
    try:
        from .config import JoplinMCPConfig

        config = JoplinMCPConfig.from_file(config_path)
        enabled_tools = config.get_enabled_tools()

        if enabled_tools:
            for tool in sorted(enabled_tools):
                print_info(f"• {tool}")
        else:
            print_warning("No tools are currently enabled")

    except Exception as e:
        # Fallback to showing all tools if config loading fails
        print_warning(f"Could not load tool configuration: {e}")
        tools = [
            "find_notes",
            "find_notes_with_tag",
            "find_notes_in_notebook",
            "get_all_notes",
            "get_note",
            "list_notebooks",
            "list_tags",
            "get_tags_by_note",
            "ping_joplin",
        ]
        print_info("Showing default read-only tools:")
        for tool in tools:
            print_info(f"• {tool}")

    print()
    print_colored("⚠️  Configuration notes:", Colors.YELLOW)
    print_info(
        "• Tool permissions and content privacy are configured during installation"
    )
    print_info("• Edit joplin-mcp.json to modify settings if needed later")
    print_info(
        "• See docs/content-privacy.md for detailed privacy controls information"
    )

    print()
    print_colored("🆘 Troubleshooting:", Colors.BOLD)
    print_info("• Make sure Joplin is running and Web Clipper is enabled")
    print_info("• Check that your API token is correct")
    print_info("• Verify port 41184 is accessible")
    if is_development:
        print_info("• See docs/troubleshooting.md for more help")
    else:
        print_info("• See package documentation for more help")


def run_installation_process(
    config_path_resolver,
    is_development: bool = False,
    welcome_message: str = "Welcome! This will configure the Joplin MCP server.",
    interfaces: List[str] = None,
) -> int:
    """Unified installation process for both development and pip installs.

    Args:
        config_path_resolver: Function that takes a token and returns a config path
        is_development: Whether this is a development install
        welcome_message: Custom welcome message
        interfaces: List of interface names to configure (default: ["claude", "jan"])

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if interfaces is None:
        interfaces = ["claude", "jan"]  # Support Claude Desktop and Jan AI by default

    print_header("Joplin MCP Server Installation")
    print_colored(welcome_message, Colors.WHITE)
    print_colored(
        "This will configure access to your Joplin notes from supported AI assistants.",
        Colors.WHITE,
    )

    try:
        # Step 1: Get Joplin API token
        token = get_token_interactively()

        # Step 2: Create/update Joplin configuration
        config_path = config_path_resolver(token)

        # Step 3: Update AI interface configurations
        interface_results = {}
        for interface_name in interfaces:
            try:
                success = update_chat_interface_config(
                    interface_name=interface_name,
                    config_path=config_path,
                    is_development=is_development,
                )
                interface_results[interface_name] = success
            except Exception as e:
                print_warning(f"Failed to configure {interface_name}: {e}")
                interface_results[interface_name] = False

        # Step 4: Test connection
        connection_ok = test_joplin_connection(config_path)

        # Step 5: Print final instructions
        print_final_instructions(config_path, interface_results, is_development)

        if not connection_ok:
            print_warning("Connection test failed, but installation completed.")
            print_info("Please check your Joplin settings and try again.")
            return 1

        return 0

    except KeyboardInterrupt:
        print_colored("\n\nInstallation cancelled by user.", Colors.YELLOW)
        return 1
    except Exception as e:
        print_error(f"Installation failed: {e}")
        import traceback

        traceback.print_exc()
        return 1
