"""Bounded inputs; provenance is assigned by the kernel, never by the documents."""

from dataclasses import dataclass
import re

from ..store.errors import StoreError

KINDS = frozenset({"GOAL", "ENTITY", "CONSTRAINT", "ASSUMPTION", "OBSERVATION", "HYPOTHESIS", "QUESTION", "ANOMALY", "OPPORTUNITY", "ARTIFACT"})
RELATIONS = frozenset({"depends_on", "derived_from", "supports", "challenges", "satisfies", "affects", "supersedes"})
DEPENDENCIES = frozenset({"depends_on", "derived_from"})


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"\S{1,128}", value):
        raise StoreError("INVALID_REFERENCE", "Identifier must contain 1..128 non-whitespace characters")
    return value


def references(items):
    if not isinstance(items, (tuple, list)) or len(items) > 256:
        raise StoreError("INVALID_REFERENCE", "At most 256 references are allowed")
    for item in items:
        identifier(item)
    if len(set(items)) != len(items):
        raise StoreError("DUPLICATE_REFERENCE", "Duplicate reference ID")
    return tuple(items)


@dataclass(frozen=True)
class Document:
    object_id: str
    kind: str
    title: str
    content: str
    links: tuple[tuple[str, str], ...] = ()
    source_ids: tuple[str, ...] = ()

    def __post_init__(self):
        identifier(self.object_id)
        if self.kind not in KINDS:
            raise StoreError("INVALID_OBJECT", "Unknown document kind")
        for value, maximum in ((self.title, 200), (self.content, 8000)):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise StoreError("INVALID_OBJECT", "Document text is missing or exceeds its size limit")
        if type(self.links) is not tuple or len(self.links) > 64 or len(set(self.links)) != len(self.links):
            raise StoreError("INVALID_OBJECT", "Links must be unique immutable pairs, at most 64")
        for relation, target in self.links:
            if relation not in RELATIONS:
                raise StoreError("INVALID_OBJECT", "Unknown relation")
            identifier(target)
        references(self.source_ids)

    def semantic(self):
        return {"object_id": self.object_id, "kind": self.kind, "content": self.content,
                "links": [list(link) for link in sorted(self.links)], "source_ids": sorted(self.source_ids)}
