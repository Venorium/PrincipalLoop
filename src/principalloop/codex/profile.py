"""Human-configured scope. Never accept a workspace or a role from a tool call.

Plugin mode locates the profile from the directory Codex starts the server in
(or the sandbox cwd Codex attaches to a call). Only a human activation creates it.
"""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from jsonschema import Draft202012Validator

from ..domain.contracts import decode_json
from ..snapshot.files import allowed_path
from ..store import StoreError
from ..store.paths import default_state_dir, private_path


PROFILE_NAME = "codex-profile.json"
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["version", "workspace", "database", "actor_id", "files", "objects"],
          "properties": {"version": {"const": 1}, "workspace": {"type": "string"}, "database": {"type": "string"},
                         "actor_id": {"type": "string", "pattern": "^cx-[a-f0-9]{16}$"},
                         "files": {"type": "array", "minItems": 1, "maxItems": 32, "uniqueItems": True, "items": {"type": "string", "minLength": 1, "maxLength": 240}},
                         "objects": {"type": "array", "maxItems": 256, "uniqueItems": True, "items": {"type": "string", "minLength": 1, "maxLength": 128}}}}


def validate_profile(data):
    if not Draft202012Validator(SCHEMA).is_valid(data):
        raise StoreError("INVALID_PROFILE", "Invalid local profile; run the human activation again.")
    if not all(Path(data[key]).is_absolute() for key in ("workspace", "database")):
        raise StoreError("INVALID_PROFILE", "The profile must fix absolute paths.")


def load_profile(path):
    data = decode_json(Path(path).read_bytes())
    validate_profile(data)
    workspace = Path(data["workspace"]).resolve(strict=True)
    private_path(Path(path), workspace)
    private_path(Path(data["database"]), workspace)
    if not workspace.is_dir():
        raise StoreError("INVALID_PROFILE", "Workspace missing.")
    # Missing authorized files are allowed here: check must report their disappearance.
    for relative in data["files"]:
        try:
            allowed_path(workspace, relative)
        except FileNotFoundError:
            pass
    return data


def same_path(first, second):
    return os.path.normcase(os.path.normpath(str(first))) == os.path.normcase(os.path.normpath(str(second)))


def profile_path_for(workspace):
    return default_state_dir(Path(workspace)) / PROFILE_NAME


def find_profile(start):
    """Nearest activated ancestor of a Codex-provided directory, or (None, None)."""
    try:
        current = Path(start).resolve(strict=True)
    except OSError:
        return None, None
    for candidate in (current, *current.parents):
        path = profile_path_for(candidate)
        if path.is_file():
            data = load_profile(path)
            if not same_path(data["workspace"], candidate):
                raise StoreError("INVALID_PROFILE", "The profile does not match this workspace; run the activation again.")
            return path, data
    return None, None


def path_from_codex(value):
    """Decode the sandbox cwd Codex sends in tool-call _meta (URI or absolute path)."""
    if not isinstance(value, str) or not value or len(value) > 4096:
        return None
    if value.startswith("file:"):
        parsed = urlparse(value)
        if parsed.netloc not in ("", "localhost"):
            return None
        value = url2pathname(unquote(parsed.path))
    path = Path(value)
    return path if path.is_absolute() else None
