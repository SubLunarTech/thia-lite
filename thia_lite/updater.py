"""
Thia-Lite Auto-Updater
========================
Checks GitHub Releases for new versions and provides
a simple self-update mechanism.

Supports:
- Version check on startup (configurable)
- One-command update via `thia-lite update`
- CI/CD friendly: GitHub Actions publish releases → users get notified
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

# GitHub repository for releases
GITHUB_REPO = "thia-libre/thia-lite"
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


async def check_for_updates(current_version: str) -> Optional[Dict[str, Any]]:
    """
    Check GitHub Releases for a newer version.

    Returns:
        None if up-to-date, or dict with:
        {
            "version": "0.2.0",
            "url": "https://github.com/...",
            "notes": "Release notes...",
            "download_url": "https://..."
        }
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                RELEASES_URL,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            latest_tag = data.get("tag_name", "").lstrip("v")

            if _version_gt(latest_tag, current_version):
                # Find the right asset for this platform
                download_url = None
                platform = _get_platform()
                for asset in data.get("assets", []):
                    name = asset.get("name", "").lower()
                    if platform == "linux" and name.endswith(".appimage"):
                        download_url = asset["browser_download_url"]
                    elif platform == "darwin" and name.endswith(".dmg"):
                        download_url = asset["browser_download_url"]
                    elif platform == "windows" and name.endswith(".exe"):
                        download_url = asset["browser_download_url"]

                return {
                    "version": latest_tag,
                    "url": data.get("html_url", ""),
                    "notes": data.get("body", "")[:500],
                    "download_url": download_url,
                    "published_at": data.get("published_at", ""),
                }

            return None

    except Exception as e:
        logger.debug(f"Update check failed: {e}")
        return None


def update_from_git() -> Tuple[bool, str]:
    """
    Update thia-lite from the Git repository (for developer installs).

    Returns (success, message).
    """
    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "pull", "--rebase"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            timeout=30,
        )

        if result.returncode == 0:
            # Re-install the package
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", ".", "-q"],
                capture_output=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                timeout=120,
            )
            return True, f"Updated successfully.\n{result.stdout.strip()}"
        else:
            return False, f"Git pull failed:\n{result.stderr.strip()}"

    except FileNotFoundError:
        return False, "Git not found. Install git or download the latest release from GitHub."
    except subprocess.TimeoutExpired:
        return False, "Update timed out. Check your network connection."
    except Exception as e:
        return False, f"Update failed: {e}"


def _version_gt(v1: str, v2: str) -> bool:
    """Compare version strings (semver-like)."""
    try:
        parts1 = [int(x) for x in v1.split(".")]
        parts2 = [int(x) for x in v2.split(".")]
        return parts1 > parts2
    except (ValueError, AttributeError):
        return False


def _get_platform() -> str:
    """Get current platform identifier."""
    if sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform == "darwin":
        return "darwin"
    elif sys.platform == "win32":
        return "windows"
    return "unknown"


def format_update_message(update: Dict[str, Any]) -> str:
    """Format update notification for display."""
    msg = f"🆕 Thia-Lite v{update['version']} is available!\n"
    if update.get("notes"):
        # First line of release notes
        first_line = update["notes"].split("\n")[0]
        msg += f"   {first_line}\n"
    msg += f"   Run: thia-lite update\n"
    msg += f"   Or visit: {update['url']}"
    return msg
