"""Human activation of a workspace, plus the optional project-scoped Codex wiring.

enable/disable only manage the private profile used by the Codex plugin.
install/uninstall additionally write a managed block in <project>/.codex/config.toml
and a repository skill (legacy mode). Neither edits the global Codex configuration.
"""

import hashlib
import json
import os
from pathlib import Path
import sys
import tomllib
from uuid import uuid4

from ..domain.types import Mode, Principal, Role
from ..snapshot.files import allowed_path
from ..store import Reader, Store, StoreError
from ..store.paths import default_state_dir, prepare_parent, private_path
from .profile import PROFILE_NAME, load_profile, validate_profile
from .skill import skill_bytes


BEGIN = "# BEGIN PrincipalLoop managed context connector\n"
END = "# END PrincipalLoop managed context connector\n"


def paths(workspace, state_dir=None):
    workspace = Path(workspace).resolve(strict=True)
    directory = state_dir or default_state_dir(workspace)
    return {"workspace": workspace, "database": private_path(directory / "control.sqlite3", workspace),
            "profile": private_path(directory / PROFILE_NAME, workspace),
            "receipt": private_path(directory / "codex-install.json", workspace),
            "config": workspace / ".codex/config.toml", "skill": workspace / ".agents/skills/principalloop/SKILL.md"}


def local_target(path, workspace):
    current = workspace
    for part in path.relative_to(workspace).parts:
        current /= part
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if current.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400 or (current.is_file() and info.st_nlink != 1):
                raise StoreError("INSTALL_PATH_DENIED", "The installation target must be an ordinary local file.")


def write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def mission(project_id, objective):
    return {"schema_version": "0.1", "project_id": project_id, "mission_revision": 1, "goal_id": "G-context",
            "objective": objective, "acceptance_criteria": ["Keep the selected context and make its changes verifiable."],
            "scope": ["workspace"], "hard_constraints": ["The connector authorizes no plan change and no external effect."],
            "allowed_actions": ["CAPTURE_CONTEXT", "INSPECT_CONTEXT"], "observable_sources": ["selected-files"],
            "budget": {"max_tokens": 0, "max_wall_seconds": 60, "max_tool_calls": 0}, "escalation_conditions": []}


def selection(workspace, files, *, allow_missing=False):
    selected = sorted(set(files))
    if not 1 <= len(selected) <= 32 or len(selected) != len(files):
        raise StoreError("INVALID_SCOPE", "Choose between 1 and 32 distinct files.")
    for relative in selected:
        if not isinstance(relative, str) or not 1 <= len(relative) <= 240:
            raise StoreError("INVALID_SCOPE", "Each path must contain between 1 and 240 characters.")
        try:
            allowed_path(workspace, relative)
        except FileNotFoundError:
            # A file still to be created stays tracked; checks will report it as missing.
            if not allow_missing:
                raise
    return selected


def _initialize(p, objective, object_ids):
    """Create or reuse the canonical mission; return the closed set of authorized objects."""
    with Store(p["database"], workspace=p["workspace"]) as store:
        if store.status()["project_id"] is None:
            if not objective:
                raise StoreError("OBJECTIVE_REQUIRED", "Provide --objective to initialize this new project.")
            project_id = "context-" + hashlib.sha256(str(p["workspace"]).encode()).hexdigest()[:16]
            store.initialize(mission(project_id, objective), Principal("local-human", Role.HUMAN, project_id), mode=Mode.COOPERATIVE)
        elif objective and store.mission()["objective"] != objective:
            raise StoreError("MISSION_CONFLICT", "The existing canonical mission is kept; use its goal.")
        return sorted(store.snapshots._closure([*object_ids, *store.snapshots.policy()["object_ids"]], store.snapshots.objects()))


def enable(workspace, *, files, object_ids=(), objective=None, state_dir=None):
    """Activate (or update) a workspace for the plugin. Keeps the installation identity."""
    p = paths(workspace, state_dir)
    selected = selection(p["workspace"], files, allow_missing=True)
    if not p["database"].exists() and not objective:
        raise StoreError("OBJECTIVE_REQUIRED", "Provide --objective to initialize this new project.")
    existing = load_profile(p["profile"]) if p["profile"].exists() else None
    prepare_parent(p["profile"])
    objects = _initialize(p, objective, [*object_ids, *(existing["objects"] if existing else [])])
    profile = {"version": 1, "workspace": str(p["workspace"]), "database": str(p["database"]),
               "actor_id": existing["actor_id"] if existing else "cx-" + uuid4().hex[:16], "files": selected, "objects": objects}
    validate_profile(profile)
    if profile != existing:
        write_atomic(p["profile"], (json.dumps(profile, indent=2, ensure_ascii=True) + "\n").encode())
    missing = [path for path in selected if not (p["workspace"] / path).is_file()]
    return {"enabled": True, "changed": profile != existing, "created": existing is None, "workspace": str(p["workspace"]),
            "files": selected, "missing_files": missing, "profile": str(p["profile"])}


def disable(workspace, state_dir=None):
    """Remove the activation. Captures and the SQLite journal are preserved."""
    p = paths(workspace, state_dir)
    if p["receipt"].exists():
        raise StoreError("INSTALL_PRESENT", "Project mode is installed: use 'principalloop codex uninstall'.")
    if not p["profile"].exists():
        return {"disabled": False, "already_disabled": True, "state_preserved": True}
    p["profile"].unlink()
    return {"disabled": True, "already_disabled": False, "state_preserved": True}


def install(workspace, *, files, object_ids=(), objective=None, state_dir=None):
    p = paths(workspace, state_dir)
    workspace = p["workspace"]
    selected = selection(workspace, files)
    for target in (p["config"], p["skill"]):
        local_target(target, workspace)
    before = p["config"].read_bytes() if p["config"].exists() else b""
    parsed = tomllib.loads(before.decode("utf-8-sig"))
    if "principalloop" in parsed.get("mcp_servers", {}):
        if p["receipt"].exists() and p["profile"].exists():
            receipt = json.loads(p["receipt"].read_text(encoding="utf-8"))
            existing = load_profile(p["profile"])
            if receipt["block"].encode() in before and existing["files"] == selected and (not object_ids or set(object_ids).issubset(existing["objects"])):
                if not p["skill"].is_file() or p["skill"].read_bytes() != skill_bytes():
                    raise StoreError("INSTALL_CONFLICT", "The installed skill is missing or different; it is preserved for review.")
                if objective:
                    with Reader(p["database"], workspace=workspace) as store:
                        if store.mission()["objective"] != objective:
                            raise StoreError("MISSION_CONFLICT", "The existing mission is different.")
                return {"installed": True, "already_installed": True, "profile": str(p["profile"]), "files": selected}
        raise StoreError("INSTALL_CONFLICT", "A PrincipalLoop configuration already exists; preserve it or uninstall its managed version.")
    if p["profile"].exists() or p["receipt"].exists():
        raise StoreError("INSTALL_CONFLICT", "This project is already enabled for the plugin; project mode is not needed. Otherwise: 'principalloop codex disable'.")
    skill_before = p["skill"].read_bytes() if p["skill"].exists() else None
    skill = skill_bytes()
    if skill_before is not None and skill_before != skill:
        raise StoreError("INSTALL_CONFLICT", "A different PrincipalLoop skill already exists; it is never overwritten automatically.")
    if not p["database"].exists() and not objective:
        raise StoreError("OBJECTIVE_REQUIRED", "Provide --objective to initialize this new project.")
    prepare_parent(p["profile"])
    objects = _initialize(p, objective, object_ids)
    profile = {"version": 1, "workspace": str(workspace), "database": str(p["database"]),
               "actor_id": "cx-" + uuid4().hex[:16], "files": selected, "objects": objects}
    validate_profile(profile)
    q = lambda value: json.dumps(value, ensure_ascii=False)
    args = ["-m", "principalloop", "codex", "serve", "--profile", str(p["profile"])]
    block = BEGIN + '[mcp_servers.principalloop]\n' + f'command = {q(sys.executable)}\nargs = {q(args)}\ncwd = {q(str(workspace))}\n' + 'startup_timeout_sec = 15\ntool_timeout_sec = 20\n' + END
    after = before + (b"\n" if before and not before.endswith(b"\n") else b"") + b"\n" + block.encode()
    tomllib.loads(after.decode("utf-8-sig"))
    receipt = {"version": 1, "block": block, "skill_owned": skill_before is None, "skill_sha256": hashlib.sha256(skill).hexdigest()}
    try:
        write_atomic(p["profile"], (json.dumps(profile, indent=2, ensure_ascii=True) + "\n").encode())
        if skill_before is None:
            write_atomic(p["skill"], skill)
        if (p["config"].read_bytes() if p["config"].exists() else b"") != before:
            raise StoreError("INSTALL_CONFLICT", "The configuration changed during installation.")
        write_atomic(p["receipt"], (json.dumps(receipt, indent=2) + "\n").encode())
        write_atomic(p["config"], after)
    except BaseException:
        # Preserve an initialized database and all observations; undo only these new files.
        p["profile"].unlink(missing_ok=True)
        p["receipt"].unlink(missing_ok=True)
        if skill_before is None and p["skill"].exists() and p["skill"].read_bytes() == skill:
            p["skill"].unlink()
        raise
    return {"installed": True, "already_installed": False, "profile": str(p["profile"]), "config": str(p["config"]), "files": selected}


def uninstall(workspace, state_dir=None, *, keep_profile=False):
    p = paths(workspace, state_dir)
    for target in (p["config"], p["skill"]):
        local_target(target, p["workspace"])
    receipt = json.loads(p["receipt"].read_text(encoding="utf-8"))
    content = p["config"].read_bytes()
    block = receipt["block"].encode()
    if content.count(block) != 1:
        raise StoreError("INSTALL_CONFLICT", "The managed block was modified; nothing is removed automatically.")
    if receipt["skill_owned"] and p["skill"].exists() and hashlib.sha256(p["skill"].read_bytes()).hexdigest() != receipt["skill_sha256"]:
        raise StoreError("INSTALL_CONFLICT", "The skill was modified; it is preserved for review.")
    remaining = content.replace(block, b"", 1)
    tomllib.loads(remaining.decode("utf-8-sig"))
    if remaining.strip():
        write_atomic(p["config"], remaining)
    else:
        p["config"].unlink()
    if receipt["skill_owned"]:
        p["skill"].unlink(missing_ok=True)
    if not keep_profile:
        p["profile"].unlink()
    p["receipt"].unlink()
    return {"removed": True, "state_preserved": True, "profile_kept": keep_profile}
