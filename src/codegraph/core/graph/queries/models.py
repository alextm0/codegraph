"""Dataclasses for graph query results."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeInfo:
    """Structured result for a single graph node."""

    qualified_name: str
    name: str
    label: str
    file_path: str


@dataclass(frozen=True)
class NodeInfoWithRel(NodeInfo):
    """NodeInfo extended with the relationship type connecting it to the queried entity."""

    relationship_type: str = ""


@dataclass(frozen=True)
class DeadCodeNode:
    """A Function or Method node with no incoming CALLS edges."""

    qualified_name: str
    name: str
    label: str
    file_path: str
    line_number: int
