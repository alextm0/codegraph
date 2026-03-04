"""IDF weights and result formatting."""

import logging
from dataclasses import dataclass
from pathlib import Path

import tiktoken

from codegraph.core.graph.ppr import PPRResult

logger = logging.getLogger(__name__)

# Shared encoder — cl100k_base is used by GPT-4 and Claude (approximate).
# Loaded once at module import; thread-safe for read-only use.
_ENCODER = tiktoken.get_encoding("cl100k_base")


@dataclass(frozen=True)
class ContextResult:
    """A single code entity with its source code, ready to serve to an AI agent."""

    entity_name: str
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
    context_items: list[ContextResult] = []
    total_tokens = 0

    for ppr in ppr_results:
        if not ppr.file_path:
            continue

        line_start, line_end = _get_node_lines(ppr)
        source_code = _read_source_lines(root, ppr.file_path, line_start, line_end)
        if source_code is None:
            continue

        tokens = count_tokens(source_code)
        item = ContextResult(
            entity_name=ppr.name,
            qualified_name=ppr.qualified_name,
            file_path=ppr.file_path,
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
# Private helpers
# ---------------------------------------------------------------------------

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
