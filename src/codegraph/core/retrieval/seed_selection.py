"""Seed selection logic."""

import logging
from dataclasses import dataclass
from neo4j import Driver
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# Default signal weights (overridden by config.yaml seed_selection section)
_DEFAULT_ENTITY_MATCH_WEIGHT: float = 0.6
_DEFAULT_BM25_WEIGHT: float = 0.3
_DEFAULT_CURRENT_FILE_WEIGHT: float = 0.1
_DEFAULT_BM25_TOP_N: int = 5


@dataclass(frozen=True)
class SeedNode:
    """A single seed with its source signal and raw weight."""

    node_id: int
    qualified_name: str
    weight: float
    source: str  # "entity_match", "bm25", "current_file"


@dataclass(frozen=True)
class PersonalizationVector:
    """Normalized seed weights ready for PPR.

    seeds maps internal Neo4j node ID -> normalized weight (sums to 1.0).
    """

    seeds: dict[int, float]


def extract_seeds(
    driver: Driver,
    task_description: str,
    mentioned_entities: list[str] | None = None,
    current_file: str | None = None,
    signal_weights: dict[str, float] | None = None,
) -> PersonalizationVector:
    """Build a personalization vector from multiple task signals.

    Args:
        driver: Active Neo4j driver.
        task_description: Free-form task text (e.g., "fix the auth timeout bug").
        mentioned_entities: Explicit entity names mentioned in the task (e.g., ["AuthService"]).
        current_file: File path the agent is currently editing. Used as a low-weight hint.
        signal_weights: Override default weights for each source signal.

    Returns:
        A PersonalizationVector whose seeds sum to 1.0.
    """
    weights = _resolve_signal_weights(signal_weights)

    all_seeds: list[SeedNode] = []

    if mentioned_entities:
        entity_seeds = _match_entities(driver, mentioned_entities, weights["entity_match"])
        all_seeds.extend(entity_seeds)
        logger.debug("Entity match seeds: %d", len(entity_seeds))

    bm25_seeds = _bm25_search(driver, task_description, weights["bm25"], weights["bm25_top_n"])
    all_seeds.extend(bm25_seeds)
    logger.debug("BM25 seeds: %d", len(bm25_seeds))

    if current_file:
        file_seeds = _current_file_seeds(driver, current_file, weights["current_file"])
        all_seeds.extend(file_seeds)
        logger.debug("Current file seeds: %d", len(file_seeds))

    if not all_seeds:
        logger.warning("extract_seeds: no seeds found for task '%s'", task_description[:80])
        return PersonalizationVector(seeds={})

    return _normalize_seeds(all_seeds)


# ---------------------------------------------------------------------------
# Private: signal extractors
# ---------------------------------------------------------------------------

def _match_entities(
    driver: Driver,
    mentioned_entities: list[str],
    base_weight: float,
) -> list[SeedNode]:
    """Match entity names against graph nodes by name or qualified_name."""
    seeds: list[SeedNode] = []
    with driver.session() as session:
        for entity in mentioned_entities:
            result = session.run(
                """
                MATCH (n)
                WHERE n.name = $name
                   OR n.qualified_name = $name
                   OR (n:Method AND (n.class_name + "." + n.name) = $name)
                RETURN id(n) AS nid, n.qualified_name AS qname
                """,
                name=entity,
            )
            for record in result:
                seeds.append(
                    SeedNode(
                        node_id=record["nid"],
                        qualified_name=record["qname"] or entity,
                        weight=base_weight,
                        source="entity_match",
                    )
                )
    if not seeds:
        logger.debug("Entity match: no nodes found for %s", mentioned_entities)
    return seeds


def _bm25_search(
    driver: Driver,
    task_description: str,
    base_weight: float,
    top_n: int,
) -> list[SeedNode]:
    """Score Function/Method nodes against task_description using BM25.

    Fetches all Function and Method nodes with their signature and docstring,
    builds an in-memory BM25 index, and returns the top_n matches.
    """
    rows = _fetch_searchable_nodes(driver)
    if not rows:
        logger.debug("BM25: no Function/Method nodes in graph")
        return []

    # Build corpus: each doc is the tokenized signature + docstring for one node.
    corpus_tokens = [_tokenize(row["signature"] + " " + row["docstring"]) for row in rows]
    query_tokens = _tokenize(task_description)

    if not any(query_tokens):
        logger.debug("BM25: empty query tokens from task description")
        return []

    bm25 = BM25Okapi(corpus_tokens)
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


def _current_file_seeds(
    driver: Driver,
    current_file: str,
    base_weight: float,
) -> list[SeedNode]:
    """Return seeds for all entities contained in current_file."""
    seeds: list[SeedNode] = []
    # Normalise to forward slashes for cross-platform matching.
    # Use ENDS WITH so callers can pass a relative suffix like
    # 'services/auth_service.py' even though the graph stores full absolute paths.
    normalised = current_file.replace("\\", "/")
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)
            WHERE replace(n.file_path, '\\\\', '/') ENDS WITH $file_path
            RETURN id(n) AS nid, n.qualified_name AS qname
            """,
            file_path=normalised,
        )
        for record in result:
            seeds.append(
                SeedNode(
                    node_id=record["nid"],
                    qualified_name=record["qname"] or "",
                    weight=base_weight,
                    source="current_file",
                )
            )
    if not seeds:
        logger.debug("Current file seeds: no nodes found for file '%s'", current_file)
    return seeds


# ---------------------------------------------------------------------------
# Private: normalization and helpers
# ---------------------------------------------------------------------------

def _normalize_seeds(all_seeds: list[SeedNode]) -> PersonalizationVector:
    """Merge duplicate node IDs (sum weights) and normalize to sum to 1.0."""
    merged: dict[int, float] = {}
    qnames: dict[int, str] = {}
    for seed in all_seeds:
        merged[seed.node_id] = merged.get(seed.node_id, 0.0) + seed.weight
        qnames[seed.node_id] = seed.qualified_name

    total = sum(merged.values())
    if total == 0.0:
        return PersonalizationVector(seeds={})

    normalized = {nid: w / total for nid, w in merged.items()}
    return PersonalizationVector(seeds=normalized)


def _fetch_searchable_nodes(driver: Driver) -> list[dict]:
    """Fetch all Function and Method nodes with their text fields for BM25 indexing."""
    rows: list[dict] = []
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)
            WHERE n:Function OR n:Method
            RETURN id(n) AS node_id,
                   n.qualified_name AS qualified_name,
                   coalesce(n.signature, "") AS signature,
                   coalesce(n.docstring, "") AS docstring
            """
        )
        for record in result:
            rows.append(
                {
                    "node_id": record["node_id"],
                    "qualified_name": record["qualified_name"] or "",
                    "signature": record["signature"] or "",
                    "docstring": record["docstring"] or "",
                }
            )
    return rows


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    import re
    # Lowercase, split on non-alphanumeric chars
    return [tok for tok in re.split(r"[^a-z0-9_]+", text.lower()) if tok]


def _resolve_signal_weights(signal_weights: dict[str, float] | None) -> dict:
    """Merge caller-supplied weights with defaults."""
    defaults: dict = {
        "entity_match": _DEFAULT_ENTITY_MATCH_WEIGHT,
        "bm25": _DEFAULT_BM25_WEIGHT,
        "current_file": _DEFAULT_CURRENT_FILE_WEIGHT,
        "bm25_top_n": _DEFAULT_BM25_TOP_N,
    }
    if signal_weights:
        defaults.update(signal_weights)
    return defaults
