"""Archive extraction — ZIP and 7z SFX."""

import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Optional


def extract_zip(zip_path: Path, dest_dir: Path) -> int:
    """Extract a ZIP archive to destination directory.

    Returns the number of files extracted.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            # Skip directories
            if info.filename.endswith("/"):
                continue
            # Normalize path separators
            name = info.filename.replace("\\", "/")
            target = dest_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    return count


def _extract_7z_with_cli(archive_path: Path, dest_dir: Path) -> Optional[int]:
    """Try extracting a .7z archive with available CLI tools."""
    for cmd in ["7z", "7za", "7zr"]:
        try:
            proc = subprocess.run(
                [cmd, "x", str(archive_path), f"-o{dest_dir}", "-y"],
                capture_output=True,
                check=False,
            )
            if proc.returncode == 0:
                return len(list(dest_dir.iterdir()))
        except FileNotFoundError:
            continue
    return None


def _extract_7z_with_py7zr(archive_path: Path, dest_dir: Path) -> Optional[int]:
    """Try extracting a .7z archive with the pure-Python py7zr library."""
    try:
        import py7zr  # type: ignore[import-untyped]

        with py7zr.SevenZipFile(archive_path, "r") as zf:
            zf.extractall(dest_dir)
        return len(list(dest_dir.iterdir()))
    except ImportError:
        return None
    except Exception:
        return None


def extract_7z_sfx(sfx_path: Path, dest_dir: Path) -> int:
    """Extract a 7z self-extracting archive.

    Tries, in order:
      1. 7z CLI (p7zip / 7zip package)
      2. py7zr (pure-Python library, pip install py7zr)
      3. Scan for embedded 7z stream and try the above again
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Try CLI tools on the SFX directly
    try:
        proc = subprocess.run(
            ["7z", "x", str(sfx_path), f"-o{dest_dir}", "-y"],
            capture_output=True,
            check=False,
        )
        if proc.returncode == 0:
            return len(list(dest_dir.iterdir()))
    except FileNotFoundError:
        pass

    # Fallback: scan for 7z magic bytes and extract the embedded stream
    _7Z_MAGIC = b"7z\xbc\xaf'\x1c"
    with open(sfx_path, "rb") as f:
        data = f.read()

    offset = data.find(_7Z_MAGIC)
    if offset < 0:
        raise ValueError(f"No 7z archive found in SFX: {sfx_path}")

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".7z", delete=False) as tmp:
        tmp.write(data[offset:])
        tmp_path = tmp.name

    try:
        arch = Path(tmp_path)
        count = _extract_7z_with_cli(arch, dest_dir)
        if count is not None:
            return count

        count = _extract_7z_with_py7zr(arch, dest_dir)
        if count is not None:
            return count

        raise RuntimeError(
            "7z / SFX アーカイブの展開には 7z コマンドが必要です。\n"
            "インストール: sudo pacman -S 7zip\n"
            "または: pip install py7zr"
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def copy_item(src: Path, dst: Path) -> int:
    """Copy a file or directory tree.

    Returns the number of files copied.
    """
    count = 0
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return 1

    if src.is_dir():
        for item in src.rglob("*"):
            if item.is_file():
                rel = item.relative_to(src)
                target = dst / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
                count += 1
    return count


def delete_item(path: Path) -> int:
    """Delete a file or directory tree.

    Returns 1 if anything was deleted.
    """
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        path.unlink()
        return 1
    if path.is_dir():
        shutil.rmtree(path)
        return 1
    return 0
