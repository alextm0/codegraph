"""Pydantic models for the visualizer API."""

from typing import Any

from pydantic import BaseModel


class InitRequest(BaseModel):
    target: str


class QueryRequest(BaseModel):
    task: str
    top_k: int = 30
    mentioned_entities: list[str] | None = None
    token_budget: int = 0


class SearchResult(BaseModel):
    qualified_name: str
    name: str
    label: str
    file_path: str


class SearchResponse(BaseModel):
    results: list[SearchResult]


class DoctorCheckResult(BaseModel):
    name: str
    ok: bool
    message: str
    fix_hint: str | None = None
    severity: str = "error"


class DoctorResponse(BaseModel):
    ok: bool
    checks: list[DoctorCheckResult]


class DeadCodeNode(BaseModel):
    qualified_name: str
    name: str
    label: str
    file_path: str


class DeadCodeResponse(BaseModel):
    results: list[DeadCodeNode]
    total: int


class StatsResponse(BaseModel):
    nodes: dict[str, int]
    edges: dict[str, int]
    most_connected_files: list[dict[str, int | str]] = []
    last_build: str | None = None


class SeedInfo(BaseModel):
    id: str
    name: str
    signal: str
    weight: float


class PPREntityResult(BaseModel):
    rank: int
    qualified_name: str
    name: str
    label: str
    file_path: str
    score: float
    path: str
    path_ids: list[str] = []
    line_number: int = 0
    line_end: int = 0
    seed_qualified_names: list[str] = []
    seed_sources: list[str] = []
    contribution: str = "graph"


class BM25FileResult(BaseModel):
    rank: int
    file_path: str


class QueryResponse(BaseModel):
    seeds: list[SeedInfo]
    ppr_results: list[PPREntityResult]
    bm25_results: list[BM25FileResult]
    graph: dict[str, list[dict]]
    damping_factor: float
    top_k: int
    git_info: dict[str, str] = {}


class NodeRelation(BaseModel):
    qualified_name: str
    name: str
    label: str
    file_path: str
    relationship: str


class NodeDetailResponse(BaseModel):
    node: dict[str, Any]
    incoming: list[NodeRelation]
    outgoing: list[NodeRelation]
    source_snippet: str | None = None


class SubgraphResponse(BaseModel):
    graph: dict[str, list[dict]]
    focus_path: str


class DependencyResult(BaseModel):
    qualified_name: str
    name: str
    label: str
    file_path: str
    relationship_type: str


class DependenciesResponse(BaseModel):
    entity: str
    direction: str
    depth: int
    results: list[DependencyResult]


class DependenciesGraphResponse(BaseModel):
    entity: str
    direction: str
    depth: int
    graph: dict[str, list[dict]]


class FileEntitySummary(BaseModel):
    qualified_name: str
    name: str
    label: str


class FileSourceResponse(BaseModel):
    file_path: str
    content: str
    line_count: int
    entities: list[FileEntitySummary] = []


class PathBetweenResponse(BaseModel):
    source: str
    target: str
    linked: bool
    path_ids: list[str] = []
    hops: int = 0
