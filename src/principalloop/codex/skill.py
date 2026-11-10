"""The plugin skill is the single source; project mode copies the same bytes."""

from functools import lru_cache
from importlib.metadata import distribution

RESOURCE = "principalloop/skills/principalloop/SKILL.md"


@lru_cache(maxsize=1)
def skill_bytes() -> bytes:
    # Packaged by hatch force-include, including editable installs (like the schemas).
    text = distribution("principalloop").locate_file(RESOURCE).read_text(encoding="utf-8")
    return text.replace("\r\n", "\n").encode("utf-8")
