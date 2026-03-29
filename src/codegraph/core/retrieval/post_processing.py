"""IDF weights and result formatting."""

import logging
from dataclasses import dataclass, replace
from pathlib import Path

import tiktoken
from neo4j import Driver
from rank_bm25 import BM25Okapi

from codegraph.core.graph.ppr import PPRResult
from codegraph.core.retrieval.seed_selection import tokenize

logger = logging.getLogger(__name__)

# Shared encoder — cl100k_base is used by GPT-4 and Claude (approximate).
# Loaded once at module import; thread-safe for read-only use.
_ENCODER = tiktoken.get_encoding("cl100k_base")

_LABEL_TO_ENTITY_TYPE: dict[str, str] = {
    "File": "file",
    "Function": "function",
    "Class": "class",
    "Method": "method",
}


@dataclass(frozen=True)
class ContextResult:
    """A single code entity with its source code, ready to serve to an AI agent."""

    entity_name: str
    entity_type: str
    qualified_name: str
    file_path: str
    line_start: int
    line_end: int
    relevance_score: float
    source_code: str
    token_count: int


def apply_idf_weights(driver) -> int:
    """Reweight all edges in Neo4j using IDF-inspired formula based on target in-degree.

    Formula: adjusted_weight = 1.0 / log2(in_degree + 2)

    This downweights "hub" nodes (e.g., utility functions called by many others)
    so PPR does not inflate their scores for unrelated seeds.

    Must be called BEFORE project_graph() so the GDS projection picks up the
    updated weights.

    Returns:
        Number of edges updated.
    """
    with driver.session() as session:
        result = session.run(
            """
            MATCH (target)
            WITH target, COUNT { (()-[]->(target)) } AS in_deg
            MATCH (src)-[r]->(target)
            SET r.weight = 1.0 / (log(toFloat(in_deg) + 2.0) / log(2.0))
            RETURN count(r) AS updated
            """
        )
        record = result.single()
        updated = record["updated"] if record else 0
        logger.info("apply_idf_weights: updated %d edges", updated)
        return updated


def reset_base_weights(driver) -> int:
    """Reset all edge weights to their original base values (undoing IDF mutation).

    CO_LOCATED edges are restored to 0.3; all other relationship types to 1.0.
    Must be called BEFORE project_graph() when apply_idf=False so the GDS
    projection is not built on stale IDF-mutated weights from a previous run.

    Returns:
        Number of edges reset.
    """
    with driver.session() as session:
        result = session.run(
            """
            MATCH ()-[r]->()
            SET r.weight = CASE type(r)
                WHEN 'CO_LOCATED' THEN 0.3
                ELSE 1.0
            END
            RETURN count(r) AS updated
            """
        )
        record = result.single()
        updated = record["updated"] if record else 0
        logger.info("reset_base_weights: reset %d edges to base weights", updated)
        return updated


def format_context(
    ppr_results: list[PPRResult],
    project_root: str,
    token_budget: int,
) -> list[ContextResult]:
    """Read source code for PPR results and accumulate until token budget is consumed.

    Results are returned in descending score order. At least one result is always
    returned (even if it alone exceeds the budget), so the caller always gets
    the most relevant entity.

    Args:
        ppr_results: Ranked PPR results (highest score first).
        project_root: Absolute path to the project root for resolving file_path.
        token_budget: Maximum total token count across all returned results.

    Returns:
        List of ContextResult in descending relevance order.
    """
    root = Path(project_root)
    deduped_results = _deduplicate_file_entities(ppr_results)
    context_items: list[ContextResult] = []
    total_tokens = 0

    for ppr in deduped_results:
        if not ppr.file_path:
            continue

        line_start, line_end = _get_node_lines(ppr)
        source_code = _read_source_lines(root, ppr.file_path, line_start, line_end)
        if not source_code:
            continue

        # file_path is already relative (stored as relative by parse_directory).
        rel_file_path = ppr.file_path

        # For File nodes entity_name == file_path; for others use entity name.
        entity_type = _LABEL_TO_ENTITY_TYPE.get(ppr.label, ppr.label.lower())
        if ppr.label == "File":
            entity_name = rel_file_path
        else:
            entity_name = ppr.name

        # qualified_name already uses the relative file prefix.
        rel_qualified_name = ppr.qualified_name

        # Fix sentinel line_end=0 for File nodes by counting actual lines.
        if line_end == 0:
            actual_lines = source_code.count("\n") + (1 if source_code else 0)
            line_end = actual_lines

        tokens = count_tokens(source_code)
        item = ContextResult(
            entity_name=entity_name,
            entity_type=entity_type,
            qualified_name=rel_qualified_name,
            file_path=rel_file_path,
            line_start=line_start,
            line_end=line_end,
            relevance_score=ppr.score,
            source_code=source_code,
            token_count=tokens,
        )

        context_items.append(item)
        total_tokens += tokens

        # Always include at least the first result even if over budget.
        if len(context_items) > 1 and total_tokens > token_budget:
            # Remove the last item we just added — it pushed us over.
            total_tokens -= tokens
            context_items.pop()
            break

    logger.info(
        "format_context: %d results, ~%d tokens (budget=%d)",
        len(context_items),
        total_tokens,
        token_budget,
    )
    return context_items


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken cl100k_base encoding (same as GPT-4 / Claude).

    Accurate to within ~1% for typical Python source code.
    """
    return len(_ENCODER.encode(text))


# ---------------------------------------------------------------------------
# Structural neighborhood expansion (SpIDER-inspired)
# ---------------------------------------------------------------------------

def expand_structural_neighbors(
    driver: Driver,
    ppr_results: list[PPRResult],
    task_description: str,
    bm25_index: BM25Okapi | None = None,
    searchable_nodes: list[dict] | None = None,
    n_centers: int = 5,
    max_depth: int = 2,
    decay: float = 0.5,
) -> list[PPRResult]:
    """Expand PPR results with structurally adjacent nodes (SpIDER-inspired).

    Takes the top n_centers PPR results as seed centers and finds nodes connected
    via CONTAINS edges within max_depth hops. These structural neighbors (co-located
    code in the same file or class) are often relevant even if they didn't score
    highly individually.

    New neighbors are scored at center_score * decay and appended after all
    original results. If a BM25 index is provided, only neighbors with a positive
    BM25 score against the task description are included as a semantic filter.

    Based on SpIDER (arXiv:2512.16956) Proposition 4.2: if relevant functions
    cluster spatially and at least one seed lands nearby, structural expansion
    improves recall.

    Args:
        driver: Active Neo4j driver.
        ppr_results: Ranked PPR results (highest score first).
        task_description: Free-form task text for optional BM25 semantic filtering.
        bm25_index: Optional pre-built BM25 index for filtering neighbors.
        searchable_nodes: Nodes corresponding to bm25_index rows (parallel list).
        n_centers: Number of top PPR results to expand from (SpIDER optimal: 5).
        max_depth: BFS depth along CONTAINS edges (2 = same-file siblings/methods).
        decay: Score factor for expanded neighbors (default 0.5 = half center score).

    Returns:
        Original results with new structural neighbors appended at the end.
        May be longer than input — callers should trim to desired top_k.
    """
    if not ppr_results:
        return ppr_results

    centers = ppr_results[:n_centers]
    existing_qnames = {r.qualified_name for r in ppr_results}

    # Build set of BM25-relevant node IDs for semantic filtering (optional)
    relevant_node_ids: set[int] | None = None
    if bm25_index is not None and searchable_nodes is not None:
        query_tokens = tokenize(task_description)
        if query_tokens:
            scores = bm25_index.get_scores(query_tokens)
            relevant_node_ids = {
                row["node_id"]
                for score, row in zip(scores, searchable_nodes)
                if score > 0.0
            }

    # Fetch structural neighbors for all centers from Neo4j
    center_qnames = [c.qualified_name for c in centers]
    center_score_map = {c.qualified_name: c.score for c in centers}
    neighbors_by_center = _fetch_contains_neighbors(
        driver, center_qnames, max_depth, existing_qnames
    )

    # Build new PPRResult objects for qualifying neighbors
    seen_new: set[str] = set()
    new_results: list[PPRResult] = []
    for center_qname, records in neighbors_by_center.items():
        center_score = center_score_map.get(center_qname, 0.0)
        for rec in records:
            qname = rec["qualified_name"]
            if qname in seen_new:
                continue
            # Semantic filter: skip nodes BM25 considers unrelated to the task
            if relevant_node_ids is not None and rec["node_id"] not in relevant_node_ids:
                continue
            seen_new.add(qname)
            new_results.append(PPRResult(
                qualified_name=qname,
                name=rec["name"],
                label=rec["label"],
                file_path=rec["file_path"],
                score=center_score * decay,
                line_start=rec.get("line_start", 0),
                line_end=rec.get("line_end", 0),
            ))

    logger.info(
        "expand_structural_neighbors: %d centers -> %d new neighbors",
        len(centers),
        len(new_results),
    )
    return ppr_results + new_results


def apply_directory_colocation_bonus(
    ppr_results: list[PPRResult],
    depth: int = 2,
    min_cluster_size: int = 2,
    bonus: float = 1.2,
) -> list[PPRResult]:
    """Boost results that cluster in the same directory (spatial proximity signal).

    If 2+ results share the same top-level directory path (default: first 2
    path segments), all results in that directory receive a score boost. This
    captures the intuition that if PPR already found several files in
    'django/db/models/', other files there are likely relevant too.

    Args:
        ppr_results: Ranked PPR results to re-score.
        depth: Number of path segments to use as the directory key.
        min_cluster_size: Minimum results in a directory to trigger the bonus.
        bonus: Score multiplier for clustered results (default 1.2 = +20%).

    Returns:
        Results re-sorted by boosted scores (stable sort, original order preserved
        within ties).
    """
    if len(ppr_results) < min_cluster_size:
        return ppr_results

    # Count results per directory prefix
    dir_counts: dict[str, int] = {}
    for ppr in ppr_results:
        if ppr.file_path:
            dir_key = _directory_key(ppr.file_path, depth)
            dir_counts[dir_key] = dir_counts.get(dir_key, 0) + 1

    # Find directories with enough results to qualify for the bonus
    clustered_dirs = {d for d, count in dir_counts.items() if count >= min_cluster_size}
    if not clustered_dirs:
        return ppr_results

    # Apply bonus and re-sort (stable: preserves original order within equal scores)
    boosted: list[PPRResult] = []
    for ppr in ppr_results:
        dir_key = _directory_key(ppr.file_path, depth) if ppr.file_path else ""
        if dir_key in clustered_dirs:
            ppr = replace(ppr, score=ppr.score * bonus)
        boosted.append(ppr)

    boosted.sort(key=lambda r: r.score, reverse=True)
    logger.debug(
        "apply_directory_colocation_bonus: %d clustered dirs, %d results re-sorted",
        len(clustered_dirs),
        len(boosted),
    )
    return boosted


def inject_directory_neighbors(
    driver: Driver,
    ppr_results: list[PPRResult],
    task_description: str,
    bm25_index: BM25Okapi | None = None,
    searchable_nodes: list[dict] | None = None,
    n_top_dirs: int = 3,
    max_inject: int = 10,
    decay: float = 0.3,
) -> list[PPRResult]:
    """Inject sibling File nodes from the top directories in the PPR results.

    After PPR, the top-k may miss gold files that share a directory with
    high-ranking results but have no explicit import/call edges connecting them.
    This function queries File nodes by path prefix (directory co-location)
    and appends candidates that score positively on BM25 against the task.

    Unlike expand_structural_neighbors (which traverses CONTAINS edges and
    stays within a single file), this function queries by file path prefix,
    finding sibling files in the same directory. See DEC-021.

    Args:
        driver: Active Neo4j driver.
        ppr_results: Current ranked results (highest score first).
        task_description: Task text for BM25 semantic filtering.
        bm25_index: Optional pre-built BM25 index for filtering.
        searchable_nodes: Nodes corresponding to bm25_index rows.
        n_top_dirs: Number of most-represented directories to expand.
        max_inject: Maximum number of new files to inject.
        decay: Score assigned to injected files as a fraction of the average
            directory score (e.g., 0.3 = 30% of avg dir PPR score).

    Returns:
        Original results with injected directory neighbors appended.
    """
    if not ppr_results:
        return ppr_results

    # Count PPR score totals per directory to find the most relevant directories
    dir_scores: dict[str, list[float]] = {}
    for r in ppr_results:
        if r.file_path and r.label == "File":
            dir_key = _directory_key(r.file_path, depth=len(r.file_path.replace("\\", "/").split("/")) - 1)
            dir_scores.setdefault(dir_key, []).append(r.score)

    # Fall back to all node types if no File nodes in results
    if not dir_scores:
        for r in ppr_results:
            if r.file_path:
                parts = r.file_path.replace("\\", "/").split("/")
                if len(parts) > 1:
                    dir_key = "/".join(parts[:-1])
                    dir_scores.setdefault(dir_key, []).append(r.score)

    if not dir_scores:
        return ppr_results

    # Pick top n_top_dirs by total score
    top_dirs = sorted(dir_scores, key=lambda d: sum(dir_scores[d]), reverse=True)[:n_top_dirs]

    existing_file_paths = {r.file_path for r in ppr_results if r.file_path}

    # Query Neo4j for all File nodes in those directories
    candidates: list[dict] = []
    with driver.session() as session:
        for dir_prefix in top_dirs:
            result = session.run(
                """
                MATCH (f:File)
                WHERE f.file_path STARTS WITH $prefix
                  AND NOT f.file_path IN $existing
                RETURN id(f) AS node_id,
                       f.qualified_name AS qualified_name,
                       f.name AS name,
                       f.file_path AS file_path
                """,
                prefix=dir_prefix + "/",
                existing=list(existing_file_paths),
            )
            for record in result:
                candidates.append({
                    "node_id": record["node_id"],
                    "qualified_name": record["qualified_name"] or "",
                    "name": record["name"] or "",
                    "file_path": record["file_path"] or "",
                    "dir": dir_prefix,
                })

    if not candidates:
        return ppr_results

    # BM25 semantic filter: keep only candidates with positive relevance score
    if bm25_index is not None and searchable_nodes is not None:
        query_tokens = tokenize(task_description)
        if query_tokens:
            candidate_node_ids = {c["node_id"] for c in candidates}
            # Map node_id -> BM25 score from the pre-built index
            scores_map: dict[int, float] = {}
            bm25_scores = bm25_index.get_scores(query_tokens)
            for score, row in zip(bm25_scores, searchable_nodes):
                if row.get("node_id") in candidate_node_ids and score > 0.0:
                    scores_map[row["node_id"]] = score
            candidates = [c for c in candidates if c["node_id"] in scores_map]

    if not candidates:
        return ppr_results

    # Assign injected score: avg PPR score of the source directory × decay
    injected: list[PPRResult] = []
    seen_fps: set[str] = set()
    for candidate in candidates[:max_inject]:
        fp = candidate["file_path"]
        if fp in seen_fps:
            continue
        seen_fps.add(fp)
        dir_avg = sum(dir_scores.get(candidate["dir"], [0.0])) / max(
            len(dir_scores.get(candidate["dir"], [1])), 1
        )
        injected.append(PPRResult(
            qualified_name=candidate["qualified_name"],
            name=candidate["name"],
            label="File",
            file_path=fp,
            score=dir_avg * decay,
        ))

    logger.info(
        "inject_directory_neighbors: %d candidates queried, %d injected",
        len(candidates),
        len(injected),
    )
    return ppr_results + injected


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _fetch_contains_neighbors(
    driver: Driver,
    center_qnames: list[str],
    max_depth: int,
    exclude_qnames: set[str],
) -> dict[str, list[dict]]:
    """Fetch nodes connected to centers via CONTAINS edges via BFS.

    Returns a dict mapping each center's qualified_name to a list of neighbor
    property dicts (node_id, qualified_name, name, label, file_path, line_start,
    line_end). Excludes nodes already in exclude_qnames.
    """
    if not center_qnames:
        return {}

    with driver.session() as session:
        result = session.run(
            """
            UNWIND $center_qnames AS cqn
            MATCH (center {qualified_name: cqn})-[:CONTAINS*1..%(depth)s]-(neighbor)
            WHERE neighbor.qualified_name IS NOT NULL
              AND NOT neighbor.qualified_name IN $exclude_qnames
            RETURN cqn AS center_qname,
                   id(neighbor) AS node_id,
                   neighbor.qualified_name AS qualified_name,
                   coalesce(neighbor.name, "") AS name,
                   labels(neighbor)[0] AS label,
                   coalesce(neighbor.file_path, "") AS file_path,
                   coalesce(neighbor.line_start, 0) AS line_start,
                   coalesce(neighbor.line_end, 0) AS line_end
            """ % {"depth": max_depth},
            center_qnames=center_qnames,
            exclude_qnames=list(exclude_qnames),
        )
        neighbors: dict[str, list[dict]] = {}
        for record in result:
            cqn = record["center_qname"]
            if cqn not in neighbors:
                neighbors[cqn] = []
            neighbors[cqn].append({
                "node_id": record["node_id"],
                "qualified_name": record["qualified_name"],
                "name": record["name"],
                "label": record["label"],
                "file_path": record["file_path"],
                "line_start": record["line_start"],
                "line_end": record["line_end"],
            })
    return neighbors


def _directory_key(file_path: str, depth: int) -> str:
    """Return the first `depth` path segments of file_path as a directory key."""
    parts = file_path.replace("\\", "/").split("/")
    return "/".join(parts[:depth])


def _deduplicate_file_entities(ppr_results: list[PPRResult]) -> list[PPRResult]:
    """Drop File results whose content is already covered by 2+ sub-entity results.

    When PPR returns both a File node and multiple functions/methods from that
    file, the File node is redundant — its source code is a superset of what
    the sub-entities already cover, wasting the token budget.

    A File is dropped when 2 or more non-File results from the same file appear
    anywhere in the ranked list.
    """
    sub_entity_count: dict[str, int] = {}
    for ppr in ppr_results:
        if ppr.label != "File" and ppr.file_path:
            sub_entity_count[ppr.file_path] = sub_entity_count.get(ppr.file_path, 0) + 1

    deduped: list[PPRResult] = []
    for ppr in ppr_results:
        if ppr.label == "File" and sub_entity_count.get(ppr.file_path, 0) >= 2:
            logger.debug(
                "Skipping duplicate File result '%s' (%d sub-entities already present)",
                ppr.file_path,
                sub_entity_count[ppr.file_path],
            )
            continue
        deduped.append(ppr)
    return deduped


def _get_node_lines(ppr: PPRResult) -> tuple[int, int]:
    """Return the (line_start, line_end) range for a PPRResult.

    File nodes span the whole file — return (1, 0) as sentinel for "read all".
    Function/Method/Class nodes carry line_start/line_end from Neo4j; fall back
    to (1, 0) if they are missing (e.g. old graph without those properties).
    """
    if ppr.label == "File":
        return 1, 0
    if ppr.line_start > 0 and ppr.line_end >= ppr.line_start:
        return ppr.line_start, ppr.line_end
    return 1, 0


def _read_source_lines(
    root: Path,
    file_path: str,
    line_start: int,
    line_end: int,
) -> str | None:
    """Read lines [line_start, line_end] (1-indexed, inclusive) from a file.

    If line_end is 0 or line_start >= line_end, reads the full file.
    Returns None if the file cannot be read.
    """
    full_path = root / file_path
    try:
        content = full_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, FileNotFoundError) as exc:
        logger.warning("format_context: cannot read '%s': %s", full_path, exc)
        return None

    if line_end > 0 and line_end >= line_start:
        lines = content.splitlines()
        # Convert to 0-indexed slice
        start_idx = max(0, line_start - 1)
        end_idx = min(len(lines), line_end)
        return "\n".join(lines[start_idx:end_idx])

    return content
