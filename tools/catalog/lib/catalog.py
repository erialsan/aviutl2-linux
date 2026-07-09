"""Catalog index management — sync, parse, and query package metadata.

Handles the actual aviutl2-catalog-data index.json format:
  [
    {
      "id": "...",
      "name": "...",
      "type": "本体|入力プラグイン|出力プラグイン|...",
      "author": "...",
      "summary": "...",
      "description": "./md/<id>.md",
      "latest-version": "v2.0.54",
      "version": [{"version":"...", "release_date":"...", "file":[{"path":"...", "XXH3_128":"..."}]}],
      "installer": {"source": {...}, "install": [...], "uninstall": [...]},
      "dependencies": [...],
      "tags": [...],
      "popularity": int,
      "trend": int,
      "niconiCommonsId": "...",
      "images": [{"thumbnail": "..."}],
      "licenses": [...],
      "releaseDate": "...",
      "packagePageUrl": "...",
      "repoURL": "..."
    }
  ]
"""

import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Optional

from . import config, i18n


# Type mapping from Japanese to English
PACKAGE_TYPE_MAP = {
    "本体": "core",
    "mod": "mod",
    "入力プラグイン": "inputPlugin",
    "出力プラグイン": "outputPlugin",
    "拡張プラグイン": "generalPlugin",
    "フィルタプラグイン": "filterPlugin",
    "スクリプト": "script",
    "カスタム": "custom",
}


def normalize_type(jp_type: str) -> str:
    return PACKAGE_TYPE_MAP.get(jp_type, jp_type or "custom")


class Catalog:
    """Manages the local catalog index cache."""

    def __init__(self, catalog_dir: Path):
        self.catalog_dir = catalog_dir
        self._index_cache: Optional[list[dict[str, Any]]] = None

    # ── HTTP helpers ──

    def _fetch_url(self, url: str) -> bytes:
        req = urllib.request.Request(url, headers={
            "User-Agent": "aviutl2-catalog-linux/0.1.0",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    # ── Sync ──

    def sync(self) -> int:
        """Download the latest index.json from the catalog-data repo.

        Returns the number of packages indexed.
        """
        remote_base = config.CATALOG_REMOTE_URL.rstrip("/")
        index_url = f"{remote_base}/index.json"
        print(i18n.msg("sync.start"))

        self.catalog_dir.mkdir(parents=True, exist_ok=True)
        data = self._fetch_url(index_url)
        index_path = self.catalog_dir / "index.json"
        index_path.write_bytes(data)

        pkgs = json.loads(data)
        self._index_cache = pkgs
        print(i18n.msg("sync.done", len(pkgs)))
        return len(pkgs)

    def _load_index(self) -> list[dict[str, Any]]:
        """Load the cached index.json."""
        if self._index_cache is not None:
            return self._index_cache

        index_path = self.catalog_dir / "index.json"
        if index_path.exists():
            try:
                self._index_cache = json.loads(index_path.read_text())
                return self._index_cache
            except (json.JSONDecodeError, OSError):
                pass
        return []

    # ── Query ──

    def load_bootstrap(self) -> list[dict[str, Any]]:
        """Return all packages with normalised fields."""
        pkgs = self._load_index()
        result = []
        for p in pkgs:
            result.append({
                "id": p.get("id", ""),
                "name": p.get("name", ""),
                "packageType": normalize_type(p.get("type", "")),
                "packageRole": "primaryPackage",
                "author": p.get("author", ""),
                "summary": p.get("summary", ""),
                "tags": p.get("tags", []),
                "latestVersion": p.get("latest-version", ""),
                "latestReleaseDate": p.get("releaseDate", ""),
                "popularity": p.get("popularity", 0),
                "trend": p.get("trend", 0),
                "niconiCommonsId": p.get("niconiCommonsId", ""),
                "description": p.get("description", ""),
                "images": p.get("images", []),
            })
        return result

    def lookup_bootstrap(self, package_id: str) -> Optional[dict[str, Any]]:
        pkgs = self.load_bootstrap()
        for p in pkgs:
            if p.get("id") == package_id:
                return p
        return None

    def load_detail(self, package_id: str) -> Optional[dict[str, Any]]:
        """Load full detail for a package from the raw index."""
        pkgs = self._load_index()
        for p in pkgs:
            if p.get("id") == package_id:
                return p
        return None

    # ── Install data ──

    def load_install_for(self, package_id: str) -> Optional[dict[str, Any]]:
        """Extract the installer data for a package."""
        pkg = self.load_detail(package_id)
        if pkg is None:
            return None

        installer = pkg.get("installer", {})
        if not installer:
            return None

        # Transform to the format expected by installer.py
        source = installer.get("source", {})
        install_steps = installer.get("install", [])
        uninstall_steps = installer.get("uninstall", [])

        # Normalize source to our internal format
        source_normalized = _normalize_source(source)

        # Normalize steps
        steps_normalized = [_normalize_step(s, pkg) for s in install_steps]
        uninstall_normalized = [_normalize_step(s, pkg) for s in uninstall_steps]

        return {
            "installation": {
                "source": source_normalized,
                "installSteps": steps_normalized,
                "uninstallSteps": uninstall_normalized,
            }
        }

    # ── Versions ──

    def load_versions_for(self, package_id: str) -> list[dict[str, Any]]:
        """Load version entries for a package."""
        pkg = self.load_detail(package_id)
        if pkg is None:
            return []

        raw = pkg.get("version", [])
        result = []
        for v in raw:
            files = []
            for f in v.get("file", []):
                files.append({
                    "path": f.get("path", ""),
                    "xxh128": f.get("XXH3_128", ""),
                })
            result.append({
                "version": v.get("version", ""),
                "releaseDate": v.get("release_date", ""),
                "files": files,
            })
        return result

    # ── Niconi Commons Export ──

    def export_niconi_ids(self, installed: dict[str, str], data_dir: Path) -> bool:
        pkgs = self.load_bootstrap()
        entries = []
        ids = []

        for p in pkgs:
            pid = p.get("id", "")
            nid = p.get("niconiCommonsId", "")
            if pid in installed and nid:
                entries.append({
                    "packageId": pid,
                    "name": p.get("name", pid),
                    "niconiCommonsId": nid,
                })
                ids.append(nid)

        if not entries:
            return False

        output = {
            "schemaVersion": 1,
            "generatedAt": "",
            "ids": ids,
            "packages": entries,
        }

        output_path = data_dir / "catalog-niconi-commons-id.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
        return True


# ── Source normalisation ──

def _normalize_source(source: dict[str, Any]) -> dict[str, Any]:
    """Convert the actual catalog-data source format to our internal format."""
    if not source:
        return {"type": "directUrl", "url": ""}

    # direct URL
    direct = source.get("direct")
    if direct:
        return {"type": "directUrl", "url": direct}

    # GitHub
    gh = source.get("github")
    if gh:
        return {
            "type": "githubRelease",
            "owner": gh.get("owner", ""),
            "repo": gh.get("repo", ""),
            "pattern": gh.get("pattern", ".*"),
        }

    # Google Drive
    gd = source.get("googleDrive")
    if gd:
        return {"type": "googleDrive", "id": gd.get("id", "")}

    # BOOTH
    booth = source.get("booth")
    if booth:
        return {"type": "booth", "url": booth.get("url", "") if isinstance(booth, dict) else booth}

    # GitHub Releases shorthand
    gh_rel = source.get("github_release") or source.get("githubRelease")
    if gh_rel:
        return {
            "type": "githubRelease",
            "owner": gh_rel.get("owner", gh_rel.get("user", "")),
            "repo": gh_rel.get("repo", ""),
            "pattern": gh_rel.get("pattern", ".*"),
        }

    # Fallback: try any string URL
    for key in ("url", "download", "src"):
        val = source.get(key)
        if val:
            return {"type": "directUrl", "url": val}

    return {"type": "directUrl", "url": ""}


def _normalize_step(step: dict[str, Any], pkg: dict[str, Any]) -> dict[str, Any]:
    """Normalise an install/uninstall step to our internal format."""
    action = step.get("action", "")
    result = {"action": action}

    if action == "download":
        pass  # Source is handled separately
    elif action == "extract":
        result["from"] = step.get("from", "")
        result["to"] = step.get("to", "")
    elif action == "extractSfx" or action == "extract_sfx":
        result["action"] = "extractSfx"
        result["from"] = step.get("from", "")
        result["to"] = step.get("to", "")
    elif action == "copy":
        result["from"] = step.get("from", "")
        result["to"] = step.get("to", "")
    elif action == "delete":
        result["path"] = step.get("path", "")
    elif action == "run":
        result["path"] = step.get("path", "")
        result["args"] = step.get("args", [])
        result["elevate"] = step.get("elevate", False)
    elif action == "runAuoSetup" or action == "run_auo_setup":
        result["action"] = "runAuoSetup"
        result["path"] = step.get("path", "")

    return result


def export_niconi_ids(cat: Catalog, installed: dict[str, str], data_dir: Path) -> bool:
    """Convenience wrapper."""
    return cat.export_niconi_ids(installed, data_dir)
