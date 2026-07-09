"""Version detection — XXH3-128 based file verification."""

import json
import subprocess
from pathlib import Path
from typing import Any, Optional

from . import catalog as cat_mod, config, paths


def calc_xxh3_hex(file_path: Path) -> Optional[str]:
    """Calculate XXH3-128 hash of a file using xxh128sum CLI."""
    if not file_path.exists() or not file_path.is_file():
        return None

    try:
        proc = subprocess.run(
            ["xxh128sum", str(file_path)],
            capture_output=True, text=True, check=True, timeout=30,
        )
        # Output format: "hexhash  filename"
        return proc.stdout.split()[0]
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError):
        return None


def detect_installed(
    catalog: cat_mod.Catalog,
    aviutl_root: Path,
    config_dir: Path,
) -> int:
    """Detect installed packages by checking files on disk against version hashes.

    Returns the number of detected packages.
    """
    bootstraps = catalog.load_bootstrap()
    installed: dict[str, str] = {}

    for pkg in bootstraps:
        pid = pkg.get("id", "")
        versions = catalog.load_versions_for(pid)
        if not versions:
            continue

        # Check versions newest-first
        found_version = None
        for ver_entry in sorted(
            versions,
            key=lambda v: v.get("releaseDate", ""),
            reverse=True,
        ):
            files = ver_entry.get("files", [])
            if not files:
                continue

            all_match = True
            for file_entry in files:
                raw_path = file_entry.get("path", "")
                expected_hash = file_entry.get("xxh128", "").lower()
                if not raw_path or not expected_hash:
                    all_match = False
                    break

                resolved = paths.resolve_macro(raw_path, aviutl_root)
                file_path = Path(resolved)

                actual_hash = calc_xxh3_hex(file_path)
                if actual_hash is None or actual_hash.lower() != expected_hash:
                    all_match = False
                    break

            if all_match:
                found_version = ver_entry.get("version", "?")
                break

        if found_version:
            installed[pid] = found_version

    # Write to installed.json
    cat_mod.installer.save_installed_map(config_dir, installed)
    return len(installed)


def load_installed_map(config_dir: Path) -> dict[str, str]:
    """Load installed packages map."""
    # Import here to avoid circular dependency
    from . import installer
    return installer.load_installed_map(config_dir)


def check_updates(
    pkgs: list[dict[str, Any]],
    installed: dict[str, str],
    catalog: cat_mod.Catalog,
) -> list[dict[str, Any]]:
    """Compare installed versions with catalog to find updates.

    Returns list of packages with available updates.
    """
    updates = []
    for pkg in pkgs:
        pid = pkg.get("id", "")
        if pid not in installed:
            continue
        installed_ver = installed[pid]
        if installed_ver == "?":
            continue

        latest = pkg.get("latestVersion", "")
        if latest and latest != installed_ver:
            updates.append(pkg)

    return updates
