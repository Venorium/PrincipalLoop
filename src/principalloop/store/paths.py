"""Local state outside the workspace. These checks are not an OS sandbox."""

import hashlib
import os
from pathlib import Path

from .errors import StoreError


def default_state_dir(workspace: Path) -> Path:
    identity = os.path.normcase(str(workspace.resolve()))
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    if os.name == "nt":
        base = Path(os.environ["LOCALAPPDATA"]) / "PrincipalLoop" / "state"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "PrincipalLoop"
    return base / key


def private_path(path: Path, workspace: Path) -> Path:
    workspace = workspace.resolve(strict=True)
    if not workspace.is_dir():
        raise StoreError("UNSAFE_PATH", "Workspace must be an existing directory")
    target = path.resolve()
    if target.is_relative_to(workspace):
        raise StoreError("UNSAFE_PATH", "State and backups must be outside the workspace")
    if str(target).startswith(("\\\\", "//")):
        raise StoreError("UNSAFE_PATH", "Network paths are unsupported")
    for name in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        value = os.environ.get(name)
        if value and target.is_relative_to(Path(value).resolve()):
            raise StoreError("UNSAFE_PATH", "State cannot be in a known synchronized directory")
    if os.name == "nt":
        import ctypes
        # DRIVE_FIXED only: mapped network and removable volumes are refused.
        if ctypes.windll.kernel32.GetDriveTypeW(str(target.anchor)) != 3:
            raise StoreError("UNSAFE_PATH", "State requires a fixed local volume")
    if target.exists() and (not target.is_file() or target.stat().st_nlink != 1):
        raise StoreError("UNSAFE_PATH", "Database must be a regular file with a single hard link")
    return target


def prepare_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
