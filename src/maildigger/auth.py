"""Gmail IMAP authentication using App Passwords."""

import imaplib
import json
from pathlib import Path

from rich.console import Console

CONFIG_DIR = Path.home() / ".config" / "maildigger"
CONFIG_PATH = CONFIG_DIR / "config.json"

console = Console(stderr=True)


def connect(email: str | None = None, password: str | None = None) -> imaplib.IMAP4_SSL:
    """Connect to Gmail IMAP with app password.

    Uses provided credentials, or falls back to saved config.
    """
    if not email or not password:
        saved = load_config()
        email = email or saved.get("email")
        password = password or saved.get("app_password")

    if not email or not password:
        raise ValueError(
            "No credentials provided or saved. "
            "Run 'maildigger auth' first."
        )

    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    imap.login(email, password)
    return imap


def save_config(email: str, app_password: str) -> None:
    """Save credentials to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({
        "email": email,
        "app_password": app_password,
    }), encoding="utf-8")
    CONFIG_PATH.chmod(0o600)


def load_config() -> dict:
    """Load saved config, or return empty dict."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def check_auth_status() -> dict:
    """Check if we can connect to Gmail."""
    config = load_config()
    if not config.get("email") or not config.get("app_password"):
        return {"authenticated": False, "reason": "No saved credentials"}

    try:
        imap = connect(config["email"], config["app_password"])
        imap.logout()
        return {"authenticated": True, "email": config["email"]}
    except imaplib.IMAP4.error as e:
        return {"authenticated": False, "reason": f"Login failed: {e}"}
    except Exception as e:
        return {"authenticated": False, "reason": str(e)}
