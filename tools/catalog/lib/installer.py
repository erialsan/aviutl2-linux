"""Installer — package install, update, and remove orchestration."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from . import archive, catalog as cat_mod, config, download, i18n, paths


def install_package(
    package_id: str,
    install_data: dict[str, Any],
    aviutl_root: Path,
    config_dir: Path,
) -> bool:
    """Execute a package installation from install data.

    Returns True on success.
    """
    settings = install_data.get("settings", install_data)
    installation = settings.get("installation", install_data)

    source = installation.get("source", {})
    steps = installation.get("installSteps", [])

    if not steps:
        raise ValueError(f"No install steps for {package_id}")

    with tempfile.TemporaryDirectory(prefix=f"catalog-{package_id}-") as tmp_dir:
        tmp = Path(tmp_dir)
        download_dir = tmp / "download"
        download_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Download if first step is 'download' or source needs resolving
        downloaded_file = None
        if source and source.get("type"):
            print(i18n.msg("download.start", source.get("type", "?")))
            downloaded_file = download.resolve_download_source(
                source, download_dir,
                progress_cb=lambda r, t: None,
            )
            print(i18n.msg("download.done", downloaded_file.name))

        # Execute install steps
        for step in steps:
            action = step.get("action", "")
            _execute_step(action, step, aviutl_root, tmp, downloaded_file)

    # Record installation
    installed = load_installed_map(config_dir)

    # Find the installed version from version data
    cat = cat_mod.Catalog(config.get_catalog_dir())
    versions = cat.load_versions_for(package_id)
    version = ""
    if versions:
        # Versions are ordered oldest-first; use the last (latest) entry
        version = versions[-1].get("version", "")

    installed[package_id] = version
    save_installed_map(config_dir, installed)

    return True


def remove_package(
    package_id: str,
    install_data: Optional[dict[str, Any]],
    aviutl_root: Path,
    config_dir: Path,
) -> bool:
    """Remove an installed package.

    If install data has uninstall steps, execute them.
    Otherwise just remove from tracking.
    """
    if install_data:
        settings = install_data.get("settings", install_data)
        installation = settings.get("installation", install_data)
        uninstall_steps = installation.get("uninstallSteps", [])

        for step in uninstall_steps:
            action = step.get("action", "")
            if action == "delete":
                raw_path = step.get("path", "")
                resolved = paths.resolve_macro(raw_path, aviutl_root)
                target = Path(resolved)
                print(f"  Deleting: {target}")
                archive.delete_item(target)
            elif action == "run":
                raw_path = step.get("path", "")
                resolved = paths.resolve_macro(raw_path, aviutl_root)
                args = step.get("args", [])
                print(f"  Running: {resolved} {' '.join(args)}")
                subprocess.run([str(resolved)] + args, check=False)

    # Remove from tracking
    installed = load_installed_map(config_dir)
    installed.pop(package_id, None)
    save_installed_map(config_dir, installed)

    return True


def _execute_step(
    action: str,
    step: dict[str, Any],
    aviutl_root: Path,
    tmp_dir: Path,
    downloaded_file: Optional[Path],
) -> None:
    """Execute a single install step."""
    if action == "download":
        # Already handled above
        return

    elif action == "extract":
        from_path = step.get("from", "")
        to_path = step.get("to", "")

        # Resolve paths with macros
        from_resolved = paths.resolve_macro(from_path, aviutl_root, tmp_dir) if from_path else ""
        to_resolved = paths.resolve_macro(to_path, aviutl_root, tmp_dir) if to_path else ""

        # Determine source
        if not from_resolved and downloaded_file:
            src = downloaded_file
        elif from_resolved:
            src = Path(from_resolved)
        else:
            # Try the download dir
            src = tmp_dir / "download"
            if not src.exists():
                src = tmp_dir

        dest = Path(to_resolved) if to_resolved else tmp_dir

        print(i18n.msg("extract.zip", src, dest))
        count = archive.extract_zip(src, dest)
        print(i18n.msg("extract.done", count))

    elif action == "extractSfx":
        from_path = step.get("from", "")
        to_path = step.get("to", "")
        from_resolved = paths.resolve_macro(from_path, aviutl_root, tmp_dir) if from_path else ""
        to_resolved = paths.resolve_macro(to_path, aviutl_root, tmp_dir) if to_path else ""

        src = Path(from_resolved) if from_resolved else downloaded_file
        if not src:
            src = tmp_dir / "download"
        dest = Path(to_resolved) if to_resolved else tmp_dir

        print(i18n.msg("extract.seven", src, dest))
        count = archive.extract_7z_sfx(src, dest)
        print(i18n.msg("extract.done", count))

    elif action == "copy":
        from_path = step.get("from", "")
        to_path = step.get("to", "")
        from_resolved = paths.resolve_macro(from_path, aviutl_root, tmp_dir)
        to_resolved = paths.resolve_macro(to_path, aviutl_root, tmp_dir)

        src = Path(from_resolved)
        dst = Path(to_resolved)
        print(f"  Copying: {src} → {dst}")
        count = archive.copy_item(src, dst)
        print(f"  Copied {count} files")

    elif action == "delete":
        raw_path = step.get("path", "")
        resolved = paths.resolve_macro(raw_path, aviutl_root, tmp_dir)
        target = Path(resolved)
        if target.exists():
            print(f"  Deleting: {target}")
            archive.delete_item(target)

    elif action == "run":
        raw_path = step.get("path", "")
        args = step.get("args", [])
        resolved = paths.resolve_macro(raw_path, aviutl_root, tmp_dir)
        safe_args = [paths.resolve_macro(a, aviutl_root, tmp_dir) for a in args]
        print(f"  Running: {resolved}")
        subprocess.run([str(resolved)] + safe_args, check=False)

    elif action == "runAuoSetup":
        raw_path = step.get("path", "")
        resolved = paths.resolve_macro(raw_path, aviutl_root, tmp_dir)
        print(f"  Running AUO setup: {resolved}")
        # Run with -aviutldir flag
        subprocess.run(
            [str(resolved), f"-aviutldir={aviutl_root}"],
            check=False,
        )

    else:
        print(f"  \x1b[33mUnknown step action: {action}\x1b[0m")


# ── Installed map management ──

def load_installed_map(config_dir: Path) -> dict[str, str]:
    """Load installed packages map from config directory."""
    path = config_dir / "installed.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_installed_map(config_dir: Path, installed: dict[str, str]) -> None:
    """Save installed packages map to config directory."""
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "installed.json"
    path.write_text(json.dumps(installed, indent=2, ensure_ascii=False) + "\n")
