"""Multi-source downloader — handles direct URL, GitHub releases, Google Drive, BOOTH."""

import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Optional

from . import i18n


ProgressCallback = Callable[[int, int], None]


def download_file(url: str, dest_path: Path, progress_cb: Optional[ProgressCallback] = None) -> Path:
    """Download a file from a direct HTTPS URL.

    Supports only https:// URLs for security.
    Reports progress via callback (bytes_read, total_bytes).
    """
    if not url.startswith("https://"):
        raise ValueError(f"Only HTTPS URLs are supported: {url[:30]}...")

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    req = urllib.request.Request(url, headers={
        "User-Agent": "aviutl2-catalog-linux/0.1.0",
    })

    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length", "0") or "0")
        read = 0
        chunk_size = 8192

        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                read += len(chunk)
                if progress_cb and total > 0:
                    progress_cb(read, total)

    return dest_path


def download_github_release(
    owner: str,
    repo: str,
    pattern: str,
    dest_path: Path,
    progress_cb: Optional[ProgressCallback] = None,
) -> Path:
    """Download the latest release asset from GitHub that matches the pattern."""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    req = urllib.request.Request(api_url, headers={
        "User-Agent": "aviutl2-catalog-linux/0.1.0",
        "Accept": "application/vnd.github+json",
    })

    with urllib.request.urlopen(req, timeout=30) as resp:
        release = json.loads(resp.read())

    assets = release.get("assets", [])
    target = None
    for asset in assets:
        name = asset.get("name", "")
        if re.search(pattern, name):
            target = asset
            break

    if not target:
        raise FileNotFoundError(
            f"No release asset matching '{pattern}' found in {owner}/{repo}"
        )

    return download_file(target["browser_download_url"], dest_path, progress_cb)


def download_google_drive(file_id: str, dest_path: Path) -> Path:
    """Download a file from Google Drive by file ID."""
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    session = urllib.request.build_opener()
    session.addheaders = [("User-Agent", "aviutl2-catalog-linux/0.1.0")]

    with session.open(url, timeout=120) as resp:
        content_disposition = resp.headers.get("Content-Disposition", "")
        # Extract filename if available
        filename_match = re.search(r'filename\*?=(?:UTF-8\'\')?([^;]+)', content_disposition)
        if filename_match:
            fn = urllib.parse.unquote(filename_match.group(1)).strip('"')
            dest_path = dest_path.parent / fn

        total = int(resp.headers.get("Content-Length", "0") or "0")
        read = 0
        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                f.write(chunk)
                read += len(chunk)

    return dest_path


def resolve_download_source(source: dict, dest_dir: Path, progress_cb=None) -> Path:
    """Resolve and download from any source type.

    Returns the path to the downloaded file.
    """
    source_type = source.get("type", "")
    dest_dir.mkdir(parents=True, exist_ok=True)

    if source_type == "directUrl":
        url = source.get("url", "")
        filename = url.rstrip("/").split("/")[-1].split("?")[0]
        dest = dest_dir / (urllib.parse.unquote(filename) if "?" not in url else "download")
        return download_file(url, dest, progress_cb)

    elif source_type == "githubRelease":
        owner = source.get("owner", "")
        repo = source.get("repo", "")
        pattern = source.get("pattern", ".*")
        dest = dest_dir / "github_release.zip"
        return download_github_release(owner, repo, pattern, dest, progress_cb)

    elif source_type == "googleDrive":
        fid = source.get("id", "")
        dest = dest_dir / "drive_download"
        return download_google_drive(fid, dest)

    elif source_type == "booth":
        url = source.get("url", "")
        filename = url.rstrip("/").split("/")[-1]
        dest = dest_dir / (filename or "booth_download")
        return download_file(url, dest, progress_cb)

    else:
        raise ValueError(f"Unknown source type: {source_type}")


# ── Import needed for urlparse ──
import urllib.parse
