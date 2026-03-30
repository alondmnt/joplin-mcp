"""Database backup tools for Joplin MCP — SQLite snapshot management."""
import datetime
import logging
import platform
import subprocess
from pathlib import Path
from typing import Annotated, Optional

from pydantic import Field

from joplin_mcp.fastmcp_server import create_tool

logger = logging.getLogger(__name__)

_BACKUP_RETENTION = 10


def _get_joplin_db_path() -> Path:
    """Return the platform-appropriate path to Joplin's SQLite database.

    Raises:
        FileNotFoundError: If the database file does not exist at the
            expected location.
    """
    system = platform.system()
    if system == "Windows":
        base = Path.home() / "AppData" / "Roaming"
    else:
        # macOS and Linux both use ~/.config
        base = Path.home() / ".config"

    db_path = base / "joplin-desktop" / "database.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(
            f"Joplin database not found at {db_path}. "
            "Is Joplin Desktop installed?"
        )
    return db_path


_BACKUP_DIR = Path.home() / "JoplinBackup" / "default" / "mcp-backups"


def backup_joplin_database(force: bool = False) -> Optional[str]:
    """Create a SQLite backup of the Joplin database.

    Uses sqlite3's .backup command for a safe, consistent snapshot even
    while Joplin Desktop is running.

    By default (force=False): creates auto-backup with once-per-day guard,
    subject to automatic retention cleanup (last N kept).

    With force=True: creates manual backup that is never auto-deleted,
    requiring explicit user cleanup.

    Args:
        force: If True, create manual backup (no daily guard, no
            auto-cleanup).

    Returns:
        Backup file path on success, None on skip or failure.
    """
    try:
        db_path = _get_joplin_db_path()
    except FileNotFoundError:
        logger.warning("Joplin database not found — skipping backup")
        return None

    _BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if force:
        # Manual backup — never auto-deleted
        backup_path = _BACKUP_DIR / f"joplin_manual_backup_{timestamp}.sqlite"
    else:
        # Auto backup — once-per-day guard
        today = datetime.date.today().strftime("%Y%m%d")
        existing = list(
            _BACKUP_DIR.glob(f"joplin_auto_backup_{today}_*.sqlite")
        )
        if existing:
            logger.info(
                f"Daily auto-backup already exists: {existing[0].name}"
            )
            return str(existing[0])
        backup_path = _BACKUP_DIR / f"joplin_auto_backup_{timestamp}.sqlite"

    try:
        result = subprocess.run(
            ["sqlite3", str(db_path), f".backup '{backup_path}'"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(f"SQLite backup failed: {result.stderr}")
            return None

        logger.info(f"Database backup created: {backup_path}")

        # Enforce retention on auto-backups only
        # (manual backups are never auto-deleted)
        if not force:
            auto_backups = sorted(
                _BACKUP_DIR.glob("joplin_auto_backup_*.sqlite"),
                reverse=True,
            )
            for old_backup in auto_backups[_BACKUP_RETENTION:]:
                old_backup.unlink()
                logger.info(f"Removed old auto-backup: {old_backup.name}")

        return str(backup_path)

    except Exception as e:
        logger.warning(f"Database backup failed: {e}")
        return None


@create_tool("backup_database", "Backup Joplin database")
async def backup_database() -> str:
    """Create a full SQLite backup of the Joplin database.

    Creates a complete snapshot of the Joplin database using SQLite's backup
    command, safe even while Joplin Desktop is running. Use before large
    reorganization operations or as a manual safety checkpoint.

    Backups are stored in ~/JoplinBackup/default/mcp-backups/ with timestamps.
    Last 10 auto-backups are retained; manual backups are never auto-deleted.

    Note: Bulk operations (search_and_bulk_update_execute, bulk_move_notes)
    trigger this automatically once per day. This tool bypasses the daily
    guard and always creates a fresh backup.

    Returns:
        str: Success message with backup path, or failure details.
    """
    try:
        db_path = _get_joplin_db_path()
    except FileNotFoundError:
        db_path = Path("~/.config/joplin-desktop/database.sqlite")

    backup_path = backup_joplin_database(force=True)
    if backup_path:
        size_mb = Path(backup_path).stat().st_size / (1024 * 1024)
        return (
            "OPERATION: BACKUP_DATABASE\n"
            "STATUS: SUCCESS\n"
            f"BACKUP_PATH: {backup_path}\n"
            f"SIZE: {size_mb:.1f} MB\n"
            f"MESSAGE: Full Joplin database backup created. Restore by "
            f"replacing {db_path} with this file (while Joplin Desktop "
            f"is closed)."
        )
    else:
        return (
            "OPERATION: BACKUP_DATABASE\n"
            "STATUS: FAILED\n"
            f"MESSAGE: Could not create database backup. Joplin database "
            f"may not exist at {db_path}. Check server logs."
        )
