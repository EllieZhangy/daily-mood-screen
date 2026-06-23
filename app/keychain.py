"""
app/keychain.py

macOS Keychain read/write via the built-in `security` CLI.
No third-party package required — works in a PyInstaller bundle.
"""

import subprocess

_ACCOUNT = "daily_mood"


def get_key(service: str) -> str | None:
    """Return the stored secret for `service`, or None if not found."""
    try:
        r = subprocess.run(
            ["security", "find-generic-password",
             "-a", _ACCOUNT, "-s", service, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or None if r.returncode == 0 else None
    except Exception:
        return None


def set_key(service: str, value: str) -> bool:
    """Store `value` under `service` in the login Keychain. Overwrites if present."""
    try:
        r = subprocess.run(
            ["security", "add-generic-password",
             "-a", _ACCOUNT, "-s", service, "-w", value, "-U"],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def delete_key(service: str) -> bool:
    """Remove the entry for `service` from the Keychain."""
    try:
        r = subprocess.run(
            ["security", "delete-generic-password",
             "-a", _ACCOUNT, "-s", service],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


# Canonical service names used everywhere
OPENAI_SERVICE     = "daily_mood.openai"
WEATHERAPI_SERVICE = "daily_mood.weatherapi"
