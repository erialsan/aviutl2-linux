"""Configuration and path management for catalog operations.

Follows XDG Base Directory Specification:
  Config: $XDG_CONFIG_HOME/aviutl2-catalog/  (~/.config/aviutl2-catalog/)
  Cache:  $XDG_CACHE_HOME/aviutl2-catalog/   (~/.cache/aviutl2-catalog/)
  Data:   $XDG_DATA_HOME/aviutl2-catalog/    (~/.local/share/aviutl2-catalog/)

Wine prefix detection:
  1. $WINEPREFIX env var
  2. Auto-detect from repo layout (pfx-ge/pfx/ relative to script)
  3. Default ~/.wine
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

# ── Remote catalog source ──
CATALOG_REMOTE_URL = os.environ.get(
    "CATALOG_REMOTE_URL",
    "https://raw.githubusercontent.com/Neosku/aviutl2-catalog-data/main/",
)


# ── Path resolution ──

def get_repo_root() -> Path:
    """Find the aviutl2-linux repo root (containing launch-ge.sh)."""
    script_dir = Path(__file__).resolve().parent.parent  # tools/catalog/
    # Walk up to find repo root (has launch-ge.sh)
    for d in [script_dir, script_dir.parent, script_dir.parent.parent]:
        if (d / "launch-ge.sh").exists():
            return d
    return script_dir.parent  # Fallback: tools/


def get_config_dir() -> Path:
    """Catalog config directory (~/.config/aviutl2-catalog/)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "aviutl2-catalog"


def get_cache_dir() -> Path:
    """Catalog cache directory (~/.cache/aviutl2-catalog/)."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "aviutl2-catalog"


def get_data_dir() -> Path:
    """Catalog data directory (~/.local/share/aviutl2-catalog/)."""
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "aviutl2-catalog"


def get_catalog_dir() -> Path:
    """Directory for catalog distribution artifacts (under cache)."""
    return get_cache_dir() / "catalog"


def get_wine_prefix() -> Optional[Path]:
    """Detect the Wine prefix path."""
    env = os.environ.get("WINEPREFIX")
    if env:
        return Path(env)

    # Auto-detect from repo layout
    repo = get_repo_root()
    pfx_ge = repo / "pfx-ge" / "pfx"
    if pfx_ge.exists():
        return pfx_ge

    # Check pfx-custom (sometimes used for user data)
    pfx_custom = repo / "pfx-custom"
    if pfx_custom.exists() and (pfx_custom / "pfx").exists():
        return pfx_custom / "pfx"

    # Check home dir
    home_pfx = Path.home() / ".wine"
    if home_pfx.exists() and (home_pfx / "drive_c").exists():
        return home_pfx

    return None


def get_aviutl_root() -> Optional[Path]:
    """Detect the AviUtl2 root directory."""
    env = os.environ.get("AVIUTL2_ROOT")
    if env:
        return Path(env)

    repo = get_repo_root()
    if (repo / "aviutl2.exe").exists():
        return repo

    # Check Wine prefix
    prefix = get_wine_prefix()
    if prefix:
        candidates = [
            prefix / "drive_c" / "Program Files" / "AviUtl2",
            prefix / "drive_c" / "ProgramData" / "aviutl2",
            prefix / "drive_c" / "users" / "steamuser" / "AppData" / "Roaming" / "aviutl2",
        ]
        for c in candidates:
            if c.exists() and any(c.glob("*.exe")):
                return c

    return None


def get_aviutl_data_dir(aviutl_root: Path) -> Path:
    """Get the AviUtl2 data directory.

    Portable mode: root/data/
    Standard mode: root (or ProgramData/aviutl2 in Wine prefix)
    """
    # Check for portable mode: data/ subdirectory
    data_dir = aviutl_root / "data"
    if data_dir.exists() and (data_dir / "Plugin").exists():
        return data_dir

    # Check ProgramData in Wine prefix
    prefix = get_wine_prefix()
    if prefix:
        progdata = prefix / "drive_c" / "ProgramData" / "aviutl2"
        if progdata.exists():
            return progdata

    # Fallback: the root itself may contain Plugin/ directory
    return aviutl_root


def get_plugin_dir(aviutl_root: Path) -> Path:
    """Get the AviUtl2 Plugin directory."""
    data = get_aviutl_data_dir(aviutl_root)
    plugin = data / "Plugin"
    plugin.mkdir(parents=True, exist_ok=True)
    return plugin


def get_script_dir(aviutl_root: Path) -> Path:
    """Get the AviUtl2 Script directory."""
    data = get_aviutl_data_dir(aviutl_root)
    script = data / "Script"
    script.mkdir(parents=True, exist_ok=True)
    return script


# ── Settings management ──

DEFAULT_SETTINGS = {
    "locale": "ja",
    "theme": "dark",
    "package_state_opt_out": False,
    "local_mode_enabled": False,
    "local_manifest_path": "",
    "package_updates_paused_ids": [],
    "deprecated_notice_dismissed_ids": [],
}


def load_settings() -> dict[str, Any]:
    """Load settings from config directory."""
    settings_file = get_config_dir() / "settings.json"
    if settings_file.exists():
        try:
            data = json.loads(settings_file.read_text())
            merged = dict(DEFAULT_SETTINGS)
            merged.update(data)
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict[str, Any]) -> None:
    """Save settings to config directory."""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_file = config_dir / "settings.json"
    settings_file.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")


# ── Initialization ──

def ensure_dirs() -> None:
    """Ensure all required directories exist."""
    get_config_dir().mkdir(parents=True, exist_ok=True)
    get_cache_dir().mkdir(parents=True, exist_ok=True)
    get_data_dir().mkdir(parents=True, exist_ok=True)
    get_catalog_dir().mkdir(parents=True, exist_ok=True)
