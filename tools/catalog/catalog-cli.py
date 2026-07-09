#!/usr/bin/env python3
"""
AviUtl2 Catalog — Linux CLI

Linux-native package manager for AviUtl2 plugins.
Replicates the Windows Tauri catalog app as a CLI tool
for use with the AviUtl2 Linux compatibility layer.

Usage:
  catalog-cli.py sync            Download catalog index
  catalog-cli.py list            List available packages
  catalog-cli.py list --installed  List installed packages
  catalog-cli.py list --updates    List packages with updates
  catalog-cli.py search <query>     Search packages
  catalog-cli.py info <id>          Show package details
  catalog-cli.py install <id>       Install a package
  catalog-cli.py update             Update all packages
  catalog-cli.py update <id>        Update a specific package
  catalog-cli.py remove <id>        Remove a package
  catalog-cli.py detect             Detect installed packages from disk
  catalog-cli.py niconi             Export niconi commons IDs
  catalog-cli.py diagnose           Collect system info

Environment:
  AVIUTL2_ROOT    — AviUtl2 install root (default: auto-detect)
  CATALOG_DIR     — Catalog config dir (default: ~/.config/aviutl2-catalog)
  WINEPREFIX      — Wine prefix path (default: auto-detect from launch-ge.sh)
  CATALOG_LOCALE  — UI locale (ja|en|ko|zh-CN|zh-TW, default: ja)
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Optional

# ── ensure we can import from lib/ ──
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import config, catalog, download, installer, detector, paths, types, i18n


def cmd_sync(args: argparse.Namespace) -> int:
    """Download catalog index from remote."""
    cat = catalog.Catalog(config.get_catalog_dir())
    try:
        count = cat.sync()
        return 0
    except Exception as e:
        print(i18n.msg("sync.error", str(e)), file=sys.stderr)
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    """List packages from the local catalog."""
    cat = catalog.Catalog(config.get_catalog_dir())
    pkgs = cat.load_bootstrap()
    if not pkgs:
        print(i18n.msg("list.empty"))
        return 0

    installed = {}
    if args.installed or args.updates:
        installed = detector.load_installed_map(config.get_config_dir())

    if args.installed:
        pkgs = [p for p in pkgs if p["id"] in installed]
    elif args.updates:
        pkgs = [p for p in pkgs if p["id"] in installed and installed[p["id"]] != "?"]
        updates = detector.check_updates(pkgs, installed, cat)
        pkgs = updates

    if not pkgs:
        print(i18n.msg("list.empty_filtered"))
        return 0

    for p in pkgs:
        ver = installed.get(p["id"], "")
        ver_str = f"  \x1b[2m[{ver}]\x1b[0m" if ver else ""
        update_str = ""
        if args.updates and installed.get(p["id"]):
            update_str = f" \x1b[33m\u2192 {p.get('latestVersion', '?')}\x1b[0m"
        print(f"  {p['id']:40s} {p.get('name', '?'):30s} {p.get('packageType', ''):15s}{ver_str}{update_str}")

    print(i18n.msg("list.count", len(pkgs)))
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Search packages by query string."""
    cat = catalog.Catalog(config.get_catalog_dir())
    pkgs = cat.load_bootstrap()
    if not pkgs:
        print(i18n.msg("list.empty"))
        return 0

    q = args.query.lower()
    matches = []
    for p in pkgs:
        name = (p.get("name") or "").lower()
        author = (p.get("author") or "").lower()
        summary = (p.get("summary") or "").lower()
        tags = " ".join(p.get("tags") or [])
        if q in name or q in author or q in summary or q in tags:
            matches.append(p)

    if not matches:
        print(i18n.msg("search.none", args.query))
        return 0

    print(i18n.msg("search.results", args.query, len(matches)))
    for p in matches:
        print(f"  {p['id']:40s} {p.get('name', '?'):30s} {p.get('packageType', ''):15s}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Show detailed package info."""
    cat = catalog.Catalog(config.get_catalog_dir())
    pkg = cat.load_detail(args.package_id)
    if not pkg:
        print(i18n.msg("info.not_found", args.package_id), file=sys.stderr)
        return 1

    bootstrap = cat.lookup_bootstrap(args.package_id)

    print(f"\n\x1b[1m{pkg.get('name', args.package_id)}\x1b[0m")
    print(f"  ID:      {args.package_id}")
    if bootstrap:
        print(f"  Type:    {bootstrap.get('packageType', '?')}")
        print(f"  Author:  {bootstrap.get('author', '?')}")
        if bootstrap.get("tags"):
            print(f"  Tags:    {', '.join(bootstrap['tags'])}")
        print(f"  Version: {bootstrap.get('latestVersion', '?')}")
    print()

    desc = pkg.get("description", "")
    if isinstance(desc, str) and desc.endswith(".md"):
        print(f"  Description: {desc}")
    elif isinstance(desc, str):
        print(f"  Description: {desc[:200]}..." if len(desc) > 200 else f"  Description: {desc}")

    # Show install info
    install_info = cat.load_install_for(args.package_id)
    if install_info:
        install = install_info.get("installation", {})
        source = install.get("source", {})
        print(f"\n  Source: {source.get('type', '?')}")
        steps = install.get("installSteps", [])
        print(f"  Install steps: {len(steps)}")
        for step in steps:
            print(f"    - {step.get('action', '?')}")

    # Check installed status
    installed = detector.load_installed_map(config.get_config_dir())
    if args.package_id in installed:
        ver = installed[args.package_id]
        print(f"\n  \x1b[32mInstalled: {ver}\x1b[0m")
        if ver and ver != "?" and bootstrap.get("latestVersion") and ver != bootstrap["latestVersion"]:
            print(f"  \x1b[33mUpdate available: {bootstrap['latestVersion']}\x1b[0m")
    else:
        print(f"\n  \x1b[2mNot installed\x1b[0m")

    print()
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    """Install a package from the catalog."""
    print(i18n.msg("install.start", args.package_id))
    cat = catalog.Catalog(config.get_catalog_dir())
    pkg = cat.load_detail(args.package_id)
    if not pkg:
        print(i18n.msg("install.not_found", args.package_id), file=sys.stderr)
        return 1

    install_data = cat.load_install_for(args.package_id)
    if not install_data:
        print(i18n.msg("install.no_install_data", args.package_id), file=sys.stderr)
        return 1

    aviutl_root = paths.get_aviutl_root()
    if not aviutl_root:
        print(i18n.msg("install.no_aviutl_root"), file=sys.stderr)
        return 1

    try:
        result = installer.install_package(
            package_id=args.package_id,
            install_data=install_data,
            aviutl_root=aviutl_root,
            config_dir=config.get_config_dir(),
        )
        if result:
            print(i18n.msg("install.done", args.package_id))
            return 0
        else:
            print(i18n.msg("install.failed", args.package_id), file=sys.stderr)
            return 1
    except Exception as e:
        print(i18n.msg("install.error", str(e)), file=sys.stderr)
        return 1


def cmd_update(args: argparse.Namespace) -> int:
    """Update installed packages."""
    cat = catalog.Catalog(config.get_catalog_dir())
    installed = detector.load_installed_map(config.get_config_dir())
    if not installed:
        print(i18n.msg("update.none_installed"))
        return 0

    pkgs = cat.load_bootstrap()
    updates = detector.check_updates(pkgs, installed, cat)

    if not updates:
        print(i18n.msg("update.up_to_date"))
        return 0

    if args.package_id:
        updates = [u for u in updates if u["id"] == args.package_id]
        if not updates:
            print(i18n.msg("update.not_available", args.package_id))
            return 0

    aviutl_root = paths.get_aviutl_root()
    if not aviutl_root:
        print(i18n.msg("install.no_aviutl_root"), file=sys.stderr)
        return 1

    success = 0
    failed = 0
    for pkg in updates:
        pid = pkg["id"]
        print(i18n.msg("update.progress", pkg.get("name", pid), installed.get(pid, "?"), pkg.get("latestVersion", "?")))
        install_data = cat.load_install_for(pid)
        if not install_data:
            print(i18n.msg("update.skipped", pid))
            failed += 1
            continue
        try:
            ok = installer.install_package(pid, install_data, aviutl_root, config.get_config_dir())
            if ok:
                success += 1
            else:
                failed += 1
        except Exception as e:
            print(i18n.msg("install.error", str(e)), file=sys.stderr)
            failed += 1

    print(i18n.msg("update.summary", success, failed))
    return 0 if failed == 0 else 1


def cmd_remove(args: argparse.Namespace) -> int:
    """Remove an installed package."""
    print(i18n.msg("remove.start", args.package_id))
    cat = catalog.Catalog(config.get_catalog_dir())
    install_data = cat.load_install_for(args.package_id)

    aviutl_root = paths.get_aviutl_root()
    if not aviutl_root:
        print(i18n.msg("install.no_aviutl_root"), file=sys.stderr)
        return 1

    try:
        result = installer.remove_package(
            package_id=args.package_id,
            install_data=install_data,
            aviutl_root=aviutl_root,
            config_dir=config.get_config_dir(),
        )
        if result:
            print(i18n.msg("remove.done", args.package_id))
            return 0
        else:
            print(i18n.msg("remove.failed", args.package_id), file=sys.stderr)
            return 1
    except Exception as e:
        print(i18n.msg("remove.error", str(e)), file=sys.stderr)
        return 1


def cmd_detect(args: argparse.Namespace) -> int:
    """Detect installed packages from disk using xxh128 hashes."""
    cat = catalog.Catalog(config.get_catalog_dir())
    aviutl_root = paths.get_aviutl_root()
    if not aviutl_root:
        print(i18n.msg("install.no_aviutl_root"), file=sys.stderr)
        return 1

    print(i18n.msg("detect.start"))
    try:
        detected = detector.detect_installed(
            catalog=cat,
            aviutl_root=aviutl_root,
            config_dir=config.get_config_dir(),
        )
        print(i18n.msg("detect.done", detected))
        return 0
    except Exception as e:
        print(i18n.msg("detect.error", str(e)), file=sys.stderr)
        return 1


def cmd_niconi(args: argparse.Namespace) -> int:
    """Export niconi commons IDs."""
    cat = catalog.Catalog(config.get_catalog_dir())
    installed = detector.load_installed_map(config.get_config_dir())
    if not installed:
        print(i18n.msg("niconi.none"))
        return 0

    aviutl_root = paths.get_aviutl_root()
    data_dir = paths.get_aviutl_data_dir(aviutl_root) if aviutl_root else None
    if not data_dir:
        data_dir = config.get_config_dir()

    try:
        result = catalog.export_niconi_ids(cat, installed, data_dir)
        if result:
            print(i18n.msg("niconi.done"))
        else:
            print(i18n.msg("niconi.none"))
        return 0
    except Exception as e:
        print(i18n.msg("niconi.error", str(e)), file=sys.stderr)
        return 1


def cmd_diagnose(args: argparse.Namespace) -> int:
    """Collect system diagnostics."""
    print(i18n.msg("diagnose.header"))
    print(f"  OS:       {sys.platform}")
    try:
        uname = os.uname()
        print(f"  Kernel:   {uname.sysname} {uname.release}")
        print(f"  Arch:     {uname.machine}")
    except Exception:
        pass

    aviutl_root = paths.get_aviutl_root()
    print(f"  AviUtl:   {aviutl_root or '(not found)'}")
    if aviutl_root:
        exe = Path(aviutl_root) / "aviutl2.exe"
        print(f"  exe:      {'exists' if exe.exists() else 'missing'}")

    prefix = paths.get_wine_prefix()
    print(f"  WinePFX:  {prefix or '(not found)'}")
    if prefix:
        pfx = Path(prefix)
        print(f"  pfx:      {'exists' if pfx.exists() else 'missing'}")
        ver_file = pfx / "version"
        if ver_file.exists():
            print(f"  version:  {ver_file.read_text().strip()}")

    cat_dir = config.get_catalog_dir()
    print(f"  Catalog:  {cat_dir}")
    installed = detector.load_installed_map(config.get_config_dir())
    print(f"  Packages: {len(installed)} installed")

    # Check zstd availability
    try:
        subprocess.run(["zstd", "--version"], capture_output=True, text=True, check=True)
        print("  zstd:     available")
    except Exception:
        print("  zstd:     \x1b[33mnot found\x1b[0m")

    print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AviUtl2 Catalog — Linux CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--locale", help="Override locale (ja/en/ko/zh-CN/zh-TW)")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("sync", help="Download catalog index")

    p_list = sub.add_parser("list", help="List packages")
    p_list.add_argument("--installed", action="store_true", help="Show installed only")
    p_list.add_argument("--updates", action="store_true", help="Show packages with updates")

    p_search = sub.add_parser("search", help="Search packages")
    p_search.add_argument("query", help="Search query")

    p_info = sub.add_parser("info", help="Show package details")
    p_info.add_argument("package_id", help="Package ID")

    p_install = sub.add_parser("install", help="Install a package")
    p_install.add_argument("package_id", help="Package ID to install")

    p_update = sub.add_parser("update", help="Update installed packages")
    p_update.add_argument("package_id", nargs="?", default=None, help="Package ID to update (default: all)")

    p_remove = sub.add_parser("remove", help="Remove a package")
    p_remove.add_argument("package_id", help="Package ID to remove")

    sub.add_parser("detect", help="Detect installed packages from disk")
    sub.add_parser("niconi", help="Export niconi commons IDs")
    sub.add_parser("diagnose", help="Collect system info")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Init locale
    if args.locale:
        i18n.set_locale(args.locale)
    else:
        i18n.set_locale(os.environ.get("CATALOG_LOCALE", "ja"))

    cmd_map = {
        "sync": cmd_sync,
        "list": cmd_list,
        "search": cmd_search,
        "info": cmd_info,
        "install": cmd_install,
        "update": cmd_update,
        "remove": cmd_remove,
        "detect": cmd_detect,
        "niconi": cmd_niconi,
        "diagnose": cmd_diagnose,
    }

    if args.command in cmd_map:
        return cmd_map[args.command](args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
