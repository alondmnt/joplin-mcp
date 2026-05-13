"""E2E test fixtures for real Joplin instance testing."""

import os
import time
from unittest.mock import patch

import pytest
from joppy.client_api import ClientApi

from joplin_mcp.config import JoplinMCPConfig


def _joplin_reachable(client: ClientApi) -> bool:
    """Check if the Joplin instance is reachable and authenticated."""
    try:
        client.ping()
        # Also verify we can make an authenticated call
        client.get_all_tags()
        return True
    except Exception:
        return False


def _wait_for_joplin(client: ClientApi, timeout: int = 30) -> bool:
    """Wait for Joplin to become reachable, retrying with backoff."""
    deadline = time.monotonic() + timeout
    delay = 1
    while time.monotonic() < deadline:
        if _joplin_reachable(client):
            return True
        time.sleep(delay)
        delay = min(delay * 2, 5)
    return False


@pytest.fixture(scope="session")
def e2e_config():
    """Build JoplinMCPConfig from E2E environment variables."""
    token = os.getenv("JOPLIN_TOKEN", "e2e_test_token")
    host = os.getenv("JOPLIN_HOST", "localhost")
    port = int(os.getenv("JOPLIN_PORT", "41184"))

    return JoplinMCPConfig(
        token=token,
        host=host,
        port=port,
        # Enable destructive tools for E2E
        tools={"delete_note": True, "delete_notebook": True, "delete_tag": True},
    )


@pytest.fixture(scope="session")
def e2e_client(e2e_config):
    """Create a real ClientApi connected to the Joplin container."""
    client = ClientApi(token=e2e_config.token, url=e2e_config.base_url)
    if not _wait_for_joplin(client):
        pytest.skip("Joplin instance not reachable — skipping E2E tests")
    return client


@pytest.fixture(autouse=True)
def _no_notebook_allowlist():
    """Override root conftest's _no_notebook_allowlist — E2E manages its own config."""
    yield


@pytest.fixture(autouse=True)
def _patch_joplin_client(e2e_config, e2e_client):
    """Patch get_joplin_client everywhere so tools talk to the real Joplin."""
    targets = [
        "joplin_mcp.fastmcp_server.get_joplin_client",
        "joplin_mcp.tools.notes.get_joplin_client",
        "joplin_mcp.tools.notebooks.get_joplin_client",
        "joplin_mcp.tools.tags.get_joplin_client",
    ]
    patches = []
    for target in targets:
        try:
            p = patch(target, return_value=e2e_client)
            p.start()
            patches.append(p)
        except ModuleNotFoundError:
            continue
        except Exception as exc:
            pytest.fail(f"Failed to patch {target} in _patch_joplin_client: {exc}")

    # Also patch _module_config so allowlist tests can work
    config_targets = [
        "joplin_mcp.tools.notes._module_config",
        "joplin_mcp.tools.notebooks._module_config",
        "joplin_mcp.tools.tags._module_config",
    ]
    for target in config_targets:
        try:
            p = patch(target, e2e_config)
            p.start()
            patches.append(p)
        except ModuleNotFoundError:
            continue
        except Exception as exc:
            pytest.fail(f"Failed to patch {target} in _patch_joplin_client: {exc}")

    yield

    for p in patches:
        p.stop()


@pytest.fixture(autouse=True)
def e2e_cleanup(e2e_client):
    """Clean up all notes, notebooks, and tags created during a test."""
    from joplin_mcp.notebook_utils import invalidate_notebook_map_cache

    # Invalidate cache before capturing state
    invalidate_notebook_map_cache()

    # Capture pre-test state; if Joplin is temporarily unavailable
    # (e.g. restarting after a crash), wait and retry
    try:
        pre_notes = {n.id for n in e2e_client.get_all_notes()}
        pre_notebooks = {n.id for n in e2e_client.get_all_notebooks()}
        pre_tags = {t.id for t in e2e_client.get_all_tags()}
    except Exception:
        # Joplin might be restarting — wait for it
        if _wait_for_joplin(e2e_client, timeout=30):
            pre_notes = {n.id for n in e2e_client.get_all_notes()}
            pre_notebooks = {n.id for n in e2e_client.get_all_notebooks()}
            pre_tags = {t.id for t in e2e_client.get_all_tags()}
        else:
            # Give up capturing state — cleanup will be best-effort
            pre_notes = set()
            pre_notebooks = set()
            pre_tags = set()

    yield

    try:
        # Delete notes first (notebooks can't be deleted if non-empty)
        for note in e2e_client.get_all_notes():
            if note.id not in pre_notes:
                try:
                    e2e_client.delete_note(note.id)
                except Exception:
                    pass

        # Delete tags
        for tag in e2e_client.get_all_tags():
            if tag.id not in pre_tags:
                try:
                    e2e_client.delete_tag(tag.id)
                except Exception:
                    pass

        # Delete notebooks (may need multiple passes for nested ones)
        for _ in range(3):
            remaining = False
            for nb in e2e_client.get_all_notebooks():
                if nb.id not in pre_notebooks:
                    try:
                        e2e_client.delete_notebook(nb.id)
                    except Exception:
                        remaining = True
            if not remaining:
                break
    except Exception:
        pass  # Joplin may be temporarily unavailable

    # Invalidate cache so next test starts fresh
    invalidate_notebook_map_cache()
