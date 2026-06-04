"""Seed selection: score graph nodes as PPR starting points.

Design notes:
- Two signals combine to form the personalization vector: entity name match
  (task description contains a known function/class name) and BM25 document
  similarity. Weights are configurable via config.yaml.
- The resulting PersonalizationVector is normalized to sum to 1.0 before PPR.
- Seed quality is the dominant factor in retrieval performance — see thesis findings.
"""

import logging
import re
from dataclasses import dataclass, field
from neo4j import Driver
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# --- Default signal weights ---
# These are overridden by the seed_selection section in config.yaml.
# entity_match: reward for task description containing a known entity name (highest weight).
# bm25: reward from BM25 document similarity score.
_DEFAULT_ENTITY_MATCH_WEIGHT: float = 0.6
_DEFAULT_BM25_WEIGHT: float = 0.3
_DEFAULT_ISSUE_HINT_WEIGHT: float = 0.2
_DEFAULT_BM25_TOP_N: int = 10

_GENERIC_ENTITY_NAMES: frozenset[str] = frozenset(
    {"logger", "utils", "helper", "helpers", "common", "base", "main", "config"}
)


_PATH_EXCLUDE_OVERRIDES: tuple[tuple[str, str], ...] = (
    ("tests/", "test"),
    ("test_", "test"),
    ("migrations/", "migration"),
    ("migration/", "migration"),
    ("admin/", "admin"),
    ("templates/", "template"),
    ("template/", "template"),
)


@dataclass(frozen=True)
class SeedNode:
    """A single seed with its source signal and raw weight."""

    node_id: int
    qualified_name: str
    weight: float
    source: str  # "entity_match", "bm25", "issue_hint"


@dataclass(frozen=False)
class PersonalizationVector:
    """Normalized seed weights ready for PPR.

    Attributes:
        seeds: Maps internal Neo4j node ID -> normalized weight (sums to 1.0).
        metadata: Maps internal node ID -> dict of {qname, source}.
    """

    seeds: dict[int, float]
    metadata: dict[int, dict[str, str]] = field(default_factory=dict)

    def normalize(self) -> None:
        """Scale weights so they sum to 1.0."""
        total = sum(self.seeds.values())
        if total == 0.0:
            return
        self.seeds = {nid: w / total for nid, w in self.seeds.items()}


def extract_seeds(
    driver: Driver,
    task_description: str,
    mentioned_entities: list[str] | None = None,
    signal_weights: dict[str, float] | None = None,
    project_scope: str | None = None,
    bm25_index: BM25Okapi | None = None,
    searchable_nodes: list[dict] | None = None,
    exclude_paths: list[str] | None = None,
) -> PersonalizationVector:
    """Build a personalization vector from multiple task signals.

    Args:
        driver: Active Neo4j driver.
        task_description: Free-form task text (e.g., "fix the auth timeout bug").
        mentioned_entities: Explicit entity names mentioned in the task (e.g., ["AuthService"]).
        signal_weights: Override default weights for each source signal.
        project_scope: Optional file path prefix. When set, only nodes whose
            file_path starts with this prefix are considered. Use to prevent
            cross-project contamination when multiple repos share one Neo4j DB.
        bm25_index: Optional pre-built BM25Okapi index for performance.
        searchable_nodes: Optional list of nodes corresponding to the bm25_index.
        exclude_paths: Path substrings that disqualify a node from being a seed
            (e.g. ["tests/", "test_"]). Excluded nodes remain in the graph and
            can still receive PPR score via edges; they are only skipped as seeds.

    Returns:
        A PersonalizationVector whose seeds sum to 1.0.
    """
    weights = _resolve_signal_weights(signal_weights)

    # Normalise project_scope to forward slashes once here so all downstream
    # Cypher queries using STARTS WITH receive a consistent path regardless of OS.
    if project_scope is not None:
        project_scope = project_scope.replace("\\", "/")

    effective_exclude = _effective_exclude_paths(task_description, exclude_paths)

    all_seeds: list[SeedNode] = []

    if mentioned_entities:
        entity_seeds = _match_entities(
            driver,
            mentioned_entities,
            weights["entity_match"],
            project_scope,
            effective_exclude,
        )
        all_seeds.extend(entity_seeds)
        logger.debug("Entity match seeds: %d", len(entity_seeds))

    path_hints = extract_path_hints(task_description)
    if path_hints and weights.get("issue_hint", 0) > 0:
        hint_seeds = _match_path_hints(
            driver,
            path_hints,
            weights["issue_hint"],
            project_scope,
            effective_exclude,
        )
        all_seeds.extend(hint_seeds)
        logger.debug("Issue path hint seeds: %d", len(hint_seeds))

    bm25_seeds = _bm25_search(
        driver,
        task_description,
        weights["bm25"],
        weights["bm25_top_n"],
        project_scope,
        bm25_index,
        searchable_nodes,
        effective_exclude,
    )
    all_seeds.extend(bm25_seeds)
    logger.debug("BM25 seeds: %d", len(bm25_seeds))

    if not all_seeds:
        logger.warning(
            "extract_seeds: no seeds found for task '%s'", task_description[:80]
        )
        return PersonalizationVector(seeds={})

    return _normalize_seeds(all_seeds)


def extract_entity_names(text: str) -> list[str]:
    """Extract likely code identifiers from free-form text.

    Finds CamelCase class names, snake_case function names, backtick-quoted
    identifiers, and dotted module paths. Common English words are not
    matched — only patterns that look like code identifiers.

    Patterns matched:
    - Multi-segment CamelCase: AuthService, BlogPost (2+ capitalized words)
    - Single-word CamelCase with internal uppercase: QuerySet, HTMLParser
    - All-caps prefix + title-case: SQLCompiler, HTTPSConnection
    - snake_case: auth_service, validate_email (at least one underscore)
    - Backtick-quoted: `models.QuerySet`, `validate_email`
    - Dotted paths: models.queryset, sql.compiler (lowercase, 2-5 segments)

    Args:
        text: Any free-form text, e.g. a task description or issue body.

    Returns:
        Deduplicated list preserving first-occurrence order.
    """
    # Multi-segment CamelCase: "AuthService", "BlogPost"
    camel_multi = re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", text)
    # Single-word CamelCase with internal uppercase transition: "QuerySet", "HTMLParser"
    # Requires a lowercase->uppercase transition (not just "Fix" or "The")
    camel_single = re.findall(r"\b[A-Z][a-z]+[A-Z]\w+\b", text)
    # All-caps prefix followed by title-case word: "SQLCompiler", "HTTPSConnection"
    camel_allcaps = re.findall(r"\b[A-Z]{2,}[A-Z][a-z]\w*\b", text)
    # snake_case: at least one underscore separating lowercase segments
    snake = re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)+\b", text)
    # Backtick-quoted identifiers (common in GitHub issue descriptions)
    backtick = re.findall(r"`([A-Za-z_][A-Za-z0-9_.]+)`", text)
    # Dotted module paths: "models.queryset", "sql.compiler" (lowercase, 2-5 segments)
    dotted = re.findall(r"\b[a-z][a-z0-9]*(?:\.[a-z][a-z0-9_]*){1,4}\b", text)

    seen: set[str] = set()
    result: list[str] = []
    for name in camel_multi + camel_single + camel_allcaps + snake + backtick + dotted:
        if name in _GENERIC_ENTITY_NAMES:
            continue
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def extract_path_hints(text: str) -> list[str]:
    """Extract file and module path hints from issue or task text."""
    hints: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        normalized = raw.strip().strip("`\"'").replace("\\", "/")
        if not normalized or normalized in seen:
            return
        if len(normalized) < 3:
            return
        seen.add(normalized)
        hints.append(normalized)

    for match in re.findall(
        r"`([^`]+\.(?:py|pyi))`|\"([^\"]+\.(?:py|pyi))\"|'([^']+\.(?:py|pyi))'",
        text,
    ):
        for group in match:
            if group:
                _add(group)

    for match in re.findall(
        r"(?:^|[\s(/])([a-zA-Z0-9_./-]+(?:/[\w.-]+)+\.py)\b", text
    ):
        _add(match)

    for match in re.findall(
        r'File "([^"]+\.py)"', text
    ):
        _add(match)

    for match in re.findall(
        r"\b([a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]+)+)\b", text
    ):
        if "/" not in match and match.count(".") >= 1:
            _add(match)

    return hints


def _effective_exclude_paths(
    task_description: str,
    exclude_paths: list[str] | None,
) -> list[str] | None:
    """Drop exclude patterns when the task text explicitly references that area."""
    if not exclude_paths:
        return exclude_paths
    lower = task_description.lower()
    effective = list(exclude_paths)
    for pattern, keyword in _PATH_EXCLUDE_OVERRIDES:
        if pattern in effective and keyword in lower:
            effective = [p for p in effective if p != pattern]
    return effective or None


def prepare_bm25_index(
    driver: Driver,
    project_scope: str | None = None,
    exclude_paths: list[str] | None = None,
) -> tuple[BM25Okapi | None, list[dict] | None]:
    """Fetch nodes and build a BM25 index once (for reuse across instances)."""
    rows = fetch_searchable_nodes(driver, project_scope, exclude_paths)
    if not rows:
        return None, None

    # Build corpus: each doc is the tokenized name + file_path + signature + docstring.
    corpus_tokens = [
        tokenize(
            row["name"]
            + " "
            + row["file_path"]
            + " "
            + row["signature"]
            + " "
            + row["docstring"]
        )
        for row in rows
    ]
    return BM25Okapi(corpus_tokens), rows


# ---------------------------------------------------------------------------
# Private: signal extractors
# ---------------------------------------------------------------------------


def _match_path_hints(
    driver: Driver,
    path_hints: list[str],
    base_weight: float,
    project_scope: str | None = None,
    exclude_paths: list[str] | None = None,
) -> list[SeedNode]:
    """Seed nodes whose file_path or qualified_name matches issue path hints."""
    matches_by_hint: dict[str, list[tuple[int, str]]] = {}
    with driver.session() as session:
        for hint in path_hints:
            result = session.run(
                """
                MATCH (n)
                WHERE (n:Function OR n:Method OR n:Class OR n:File)
                  AND (
                    n.file_path CONTAINS $hint
                    OR n.qualified_name CONTAINS $hint
                  )
                  AND ($scope IS NULL OR n.file_path STARTS WITH $scope)
                  AND ($exclude_paths IS NULL OR
                       NOT any(pattern IN $exclude_paths
                               WHERE n.file_path CONTAINS pattern))
                RETURN id(n) AS nid, n.qualified_name AS qname
                ORDER BY
                  CASE WHEN n.file_path ENDS WITH $hint THEN 0 ELSE 1 END,
                  n.file_path
                LIMIT 20
                """,
                hint=hint,
                scope=project_scope,
                exclude_paths=exclude_paths or [],
            )
            records = [(r["nid"], r["qname"] or hint) for r in result]
            if records:
                matches_by_hint[hint] = records

    seeds: list[SeedNode] = []
    for hint, records in matches_by_hint.items():
        per_node_weight = base_weight / len(records)
        for nid, qname in records:
            seeds.append(
                SeedNode(
                    node_id=nid,
                    qualified_name=qname,
                    weight=per_node_weight,
                    source="issue_hint",
                )
            )
    return seeds


def _match_entities(
    driver: Driver,
    mentioned_entities: list[str],
    base_weight: float,
    project_scope: str | None = None,
    exclude_paths: list[str] | None = None,
) -> list[SeedNode]:
    """Match entity names against graph nodes with per-entity mass capping.

    Total mass per entity name is capped at base_weight and split evenly
    across all matches. This prevents ambiguous names (e.g. "fit" with 30
    matches) from receiving more aggregate seed mass than unique names.
    """
    # Collect all matches per entity name before assigning weights
    matches_by_entity: dict[str, list[tuple[int, str]]] = {}
    with driver.session() as session:
        for entity in mentioned_entities:
            result = session.run(
                """
                MATCH (n)
                WHERE (n.name = $name
                   OR n.qualified_name = $name
                   OR (n:Method AND (n.class_name + "." + n.name) = $name))
                  AND ($scope IS NULL OR n.file_path STARTS WITH $scope)
                  AND ($exclude_paths IS NULL OR
                       NOT any(pattern IN $exclude_paths WHERE n.file_path CONTAINS pattern))
                RETURN id(n) AS nid, n.qualified_name AS qname
                """,
                name=entity,
                scope=project_scope,
                exclude_paths=exclude_paths or [],
            )
            records = [(r["nid"], r["qname"] or entity) for r in result]
            if records:
                matches_by_entity[entity] = records

    # Assign weights: cap total mass per entity at base_weight, distributed evenly.
    # This prevents common generic names (e.g. "fit" with 30 matches) from receiving
    # more aggregate seed mass than rare, precise names. See fix for CR-17.
    seeds: list[SeedNode] = []
    for entity, records in matches_by_entity.items():
        n_matches = len(records)
        # Total mass is always base_weight; split evenly across all matches.
        per_node_weight = base_weight / n_matches
        for nid, qname in records:
            seeds.append(
                SeedNode(
                    node_id=nid,
                    qualified_name=qname,
                    weight=per_node_weight,
                    source="entity_match",
                )
            )

    if not seeds:
        logger.debug("Entity match: no nodes found for %s", mentioned_entities)
    else:
        logger.debug(
            "Entity match: %d seeds from %d entities",
            len(seeds),
            len(matches_by_entity),
        )
    return seeds


def _bm25_search(
    driver: Driver,
    task_description: str,
    base_weight: float,
    top_n: int,
    project_scope: str | None = None,
    bm25_index: BM25Okapi | None = None,
    searchable_nodes: list[dict] | None = None,
    exclude_paths: list[str] | None = None,
) -> list[SeedNode]:
    """Score graph nodes against task_description using BM25.

    Fetches all Function, Method, Class, and File nodes with their name,
    file_path, signature, and docstring, builds an in-memory BM25 index,
    and returns the top_n matches.
    """
    if bm25_index is not None and searchable_nodes is not None:
        bm25 = bm25_index
        rows = searchable_nodes
    else:
        rows = fetch_searchable_nodes(driver, project_scope, exclude_paths)
        if not rows:
            logger.debug("BM25: no nodes in graph")
            return []
        corpus_tokens = [
            tokenize(
                row["name"]
                + " "
                + row["file_path"]
                + " "
                + row["signature"]
                + " "
                + row["docstring"]
            )
            for row in rows
        ]
        bm25 = BM25Okapi(corpus_tokens)

    query_tokens = tokenize(task_description)
    if not any(query_tokens):
        logger.debug("BM25: empty query tokens from task description")
        return []

    scores = bm25.get_scores(query_tokens)

    # Pair rows with scores, sort descending, take top_n
    ranked = sorted(zip(scores, rows), key=lambda x: x[0], reverse=True)[:top_n]

    seeds: list[SeedNode] = []
    for score, row in ranked:
        if score <= 0.0:
            continue
        # Scale BM25 score to [0, base_weight] proportionally
        seeds.append(
            SeedNode(
                node_id=row["node_id"],
                qualified_name=row["qualified_name"],
                weight=base_weight * score,
                source="bm25",
            )
        )
    return seeds


# ---------------------------------------------------------------------------
# Private: normalization and helpers
# ---------------------------------------------------------------------------


def _normalize_seeds(all_seeds: list[SeedNode]) -> PersonalizationVector:
    """Merge duplicate node IDs (sum weights) and normalize to sum to 1.0."""
    merged: dict[int, float] = {}
    metadata: dict[int, dict[str, str]] = {}
    for seed in all_seeds:
        merged[seed.node_id] = merged.get(seed.node_id, 0.0) + seed.weight
        # Prefer entity_match > issue_hint > bm25 for provenance display.
        precedence = {"entity_match": 3, "issue_hint": 2, "bm25": 1}
        current = metadata.get(seed.node_id)
        if not current or precedence.get(seed.source, 0) >= precedence.get(
            current["source"], 0
        ):
            metadata[seed.node_id] = {
                "qname": seed.qualified_name,
                "source": seed.source,
            }

    total = sum(merged.values())
    if total == 0.0:
        return PersonalizationVector(seeds={}, metadata={})

    normalized = {nid: w / total for nid, w in merged.items()}
    return PersonalizationVector(seeds=normalized, metadata=metadata)


def fetch_searchable_nodes(
    driver: Driver,
    project_scope: str | None = None,
    exclude_paths: list[str] | None = None,
) -> list[dict]:
    """Fetch all searchable nodes with their text fields for BM25 indexing.

    Includes Function, Method, Class, and File nodes. File paths and node
    names are included so BM25 can match bug reports that reference module
    paths or class names, not just function signatures and docstrings.

    Args:
        exclude_paths: Path substrings to exclude from results (e.g. ["tests/", "test_"]).
            Any node whose file_path contains one of these substrings is omitted.
    """
    rows: list[dict] = []
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)
            WHERE (n:Function OR n:Method OR n:Class OR n:File)
              AND ($scope IS NULL OR n.file_path STARTS WITH $scope)
              AND ($exclude_paths IS NULL OR
                   NOT any(pattern IN $exclude_paths WHERE n.file_path CONTAINS pattern))
            RETURN id(n) AS node_id,
                   n.qualified_name AS qualified_name,
                   coalesce(n.name, "") AS name,
                   coalesce(n.file_path, "") AS file_path,
                   coalesce(n.signature, "") AS signature,
                   coalesce(n.docstring, "") AS docstring,
                   labels(n)[0] AS label
            """,
            scope=project_scope,
            exclude_paths=exclude_paths or [],
        )
        for record in result:
            rows.append(
                {
                    "node_id": record["node_id"],
                    "qualified_name": record["qualified_name"] or "",
                    "name": record["name"] or "",
                    "file_path": record["file_path"] or "",
                    "signature": record["signature"] or "",
                    "docstring": record["docstring"] or "",
                    "label": record["label"] or "",
                }
            )
    return rows


def tokenize(text: str) -> list[str]:
    """Tokenize text for BM25 with compound identifier splitting.

    Splits CamelCase identifiers ("SQLCompiler" -> "sql compiler") and
    snake_case ("handle_subquery" -> "handle subquery") so BM25 can match
    partial identifier tokens against bug report terms.

    Returns:
        List of lowercase tokens with length > 1 (filters single chars).
    """
    # Split CamelCase: "SQLCompiler" -> "SQL Compiler", "handleSubQuery" -> "handle Sub Query"
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", text)
    # Split on all non-alphanumeric (underscores split too, unlike before)
    tokens = re.split(r"[^a-z0-9]+", text.lower())
    return [tok for tok in tokens if len(tok) > 1]


def _resolve_signal_weights(signal_weights: dict[str, float] | None) -> dict:
    """Merge caller-supplied weights with defaults, clamping invalid values."""
    defaults: dict = {
        "entity_match": _DEFAULT_ENTITY_MATCH_WEIGHT,
        "bm25": _DEFAULT_BM25_WEIGHT,
        "issue_hint": _DEFAULT_ISSUE_HINT_WEIGHT,
        "bm25_top_n": _DEFAULT_BM25_TOP_N,
    }
    if not signal_weights:
        return defaults

    merged = dict(defaults)
    for key, value in signal_weights.items():
        if key == "bm25_top_n":
            int_val = int(value)
            if int_val < 1:
                logger.warning(
                    "Invalid bm25_top_n=%r; must be >= 1. Using default %d.",
                    value,
                    _DEFAULT_BM25_TOP_N,
                )
                merged[key] = _DEFAULT_BM25_TOP_N
            else:
                merged[key] = int_val
        else:
            if value < 0.0:
                logger.warning(
                    "Invalid signal weight %s=%r; must be >= 0. Using default.",
                    key,
                    value,
                )
            else:
                merged[key] = value
    return merged
