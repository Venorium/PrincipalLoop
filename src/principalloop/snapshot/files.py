"""Explicit, bounded and verified reads. No automatic scan of the workspace."""

import hashlib
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat

from ..store.errors import StoreError

MAX_FILE = 1024 * 1024
MAX_TOTAL = 8 * MAX_FILE
MAX_FILES = 64
EXCLUDED = frozenset({".git", ".tools", ".ssh", ".aws", ".azure", "node_modules", "__pycache__", ".codex",
                      "credentials", "credentials.json", "secrets.json", "auth.json", "id_rsa", "id_ed25519"})


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def allowed_path(workspace: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise StoreError("PATH_DENIED", "Use a workspace-relative path with forward slashes")
    parts = PurePosixPath(relative).parts
    if PurePosixPath(relative).as_posix() != relative:
        raise StoreError("PATH_DENIED", "Use a canonical relative path, without dot or empty segments")
    if PurePosixPath(relative).is_absolute() or PureWindowsPath(relative).is_absolute() or ".." in parts:
        raise StoreError("PATH_DENIED", "Paths outside the workspace are forbidden")
    for part in parts:
        lower = part.casefold()
        if lower in EXCLUDED or lower.startswith((".env", ".venv")) or lower.endswith((".pem", ".key", ".p12", ".sqlite3", ".sqlite3-wal", ".sqlite3-shm")):
            raise StoreError("PATH_DENIED", "Private, generated or credential path excluded")
    current = workspace
    for part in parts:
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise StoreError("PATH_DENIED", "Symbolic links and reparse points are not captured")
    if not current.resolve().is_relative_to(workspace.resolve()):
        raise StoreError("PATH_DENIED", "Resolved path escaped the workspace")
    return current


def read_checked(workspace: Path, relative: str):
    target = allowed_path(workspace, relative)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise StoreError("PATH_DENIED", "Only regular files with one hard link are accepted")
        if before.st_size > MAX_FILE:
            raise StoreError("CAPTURE_TOO_LARGE", "An artifact exceeds 1 MiB")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise StoreError("CAPTURE_TOO_LARGE", "An artifact exceeds 1 MiB")
        after = os.fstat(descriptor)
        path_after = allowed_path(workspace, relative).stat()
        signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
        # Windows may expose different ctime semantics through fstat and path.stat.
        # Compare ctime only on the same descriptor; identity + mtime + both hashes
        # protect the path check without treating creation time as modification time.
        stable = signature(before) == signature(after) == signature(path_after) and before.st_ctime_ns == after.st_ctime_ns
        return data, stable
    finally:
        os.close(descriptor)
