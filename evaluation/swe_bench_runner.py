"""SWE-bench benchmark runner for CodeGraph.

Entry point:
    python -m evaluation.swe_bench_runner \\
        --cache-dir .codegraph_cache \\
        --output evaluation/results/run_001 \\
        [--limit 5]           # pilot run on first N instances
        [--ablation baseline] # which AblationConfig to use (default: baseline)
        [--grouping repo_commit|none]  # group instances by (repo, base_commit) (default: repo_commit)
        [--no-grouping]       # alias for --grouping none

Data flow per instance:
    1. repo_manager.clone_or_cache() + checkout_commit()
    2. parse_directory(repo_path)
    3. clear_database() + build_graph(driver, entities)
    4. extract_seeds() + ensure_graph_ready() + run_ppr_from_node_ids()
    5. predicted_files = ranked file paths from ALL top-k PPR results
       (NOT limited by token budget — evaluation needs the full ranked list)
    6. Compare predicted_files vs gold_files (from patch)
    7. Write per_instance.jsonl + summary.json

Grouping optimisation:
    Many SWE-bench Lite instances share the same (repo, base_commit).  By
    default the runner groups them: checkout + parse + build once per group,
    then runs the cheap query step once per instance.  Use --no-grouping (or
    --grouping none) to disable and process each instance independently.
"""

import argparse
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from codegraph.core.graph.graph_builder import build_graph, clear_database
from codegraph.core.graph.ppr import create_gds_client, run_ppr_from_node_ids, drop_projection
from codegraph.core.graph.connection import create_driver, load_config
from codegraph.core.parser.python_parser import create_parser, parse_directory
from codegraph.core.retrieval.pipeline import ensure_graph_ready
from codegraph.core.retrieval.post_processing import (
    apply_directory_colocation_bonus,
    apply_idf_weights,
    expand_structural_neighbors,
)
from codegraph.core.retrieval.seed_selection import extract_entity_names, extract_seeds, prepare_bm25_index

from evaluation.ablations import ABLATIONS, AblationConfig
from evaluation.gold_patch_parser import extract_gold_files
from evaluation.metrics import aggregate_metrics, mrr, recall_at_k
from evaluation.repo_manager import checkout_commit, clone_or_cache

logger = logging.getLogger(__name__)

# SWE-bench Lite dataset identifier on Hugging Face
_SWE_BENCH_DATASET = "princeton-nlp/SWE-bench_Lite"

# ── Grouping types ────────────────────────────────────────────────────────────

GroupKey = tuple[str, str]  # (repo, base_commit)


@dataclass
class InstanceGroup:
    key: GroupKey
    instances: list[tuple[int, dict]] = field(default_factory=list)  # (original_dataset_index, instance_dict)


def _group_instances(indexed_instances: list[tuple[int, dict]]) -> list[InstanceGroup]:
    """Group indexed instances by (repo, base_commit).

    Returns groups sorted by the smallest original index in each group so that
    execution order is deterministic and matches dataset order.
    """
    groups: dict[GroupKey, InstanceGroup] = {}
    for idx, inst in indexed_instances:
        key: GroupKey = (inst["repo"], inst["base_commit"])
        if key not in groups:
            groups[key] = InstanceGroup(key=key)
        groups[key].instances.append((idx, inst))

    # Sort groups by the minimum original index in each group.
    return sorted(groups.values(), key=lambda g: min(i for i, _ in g.instances))


def _flush_ordered(buffer: dict[int, dict], next_idx: int, fh, force_all: bool = False) -> int:
    """Write contiguous results from buffer to JSONL in dataset order.

    Writes all entries starting at next_idx as long as they are present in the
    buffer.  Stops at the first gap unless force_all is True (which writes all
    buffered entries sorted by key regardless of gaps).

    Returns the updated next_idx.
    """
    if force_all:
        for idx in sorted(buffer.keys()):
            fh.write(json.dumps(buffer[idx]) + "\n")
        fh.flush()
        buffer.clear()
        return next_idx

    while next_idx in buffer:
        fh.write(json.dumps(buffer.pop(next_idx)) + "\n")
        next_idx += 1
    fh.flush()
    return next_idx


# ── Dataset loading ───────────────────────────────────────────────────────────

def _load_dataset(split: str = "test") -> list[dict]:
    """Load SWE-bench Lite instances from Hugging Face datasets."""
    try:
        from datasets import load_dataset  # type: ignore[import]
    except ImportError:
        raise ImportError(
            "Install bench extras: pip install 'codegraph[bench]'"
        )
    ds = load_dataset(_SWE_BENCH_DATASET, split=split)
    return list(ds)


def _verify_db_empty(driver) -> None:
    """Raise if the database still contains nodes after clear_database()."""
    with driver.session() as session:
        record = session.run("MATCH (n) RETURN 1 LIMIT 1").single()
        if record is not None:
            raise RuntimeError("Database not empty after clear_database()")


# ── Per-group setup ───────────────────────────────────────────────────────────

def setup_group(
    group_key: GroupKey,
    driver,
    gds,
    parser,
    cache_dir: str,
    ablation: AblationConfig,
    retriever: str,
) -> tuple[int, str, any, any]:
    """Clone/cache, checkout, parse, build graph for a (repo, base_commit) group.

    Returns (total_nodes, repo_path, bm25_index, searchable_nodes).
    Raises on any failure — caller is responsible for error handling.
    """
    repo, base_commit = group_key
    repo_url = f"https://github.com/{repo}"

    # Ensure any stale projections are cleared before setup
    drop_projection(gds)

    repo_path = clone_or_cache(repo_url, cache_dir)
    checkout_commit(repo_path, base_commit)

    entities = parse_directory(repo_path, parser, exclude_patterns=["tests", ".git"])

    clear_database(driver)
    _verify_db_empty(driver)
    counts = build_graph(driver, entities)
    total_nodes = sum(counts.values())

    bm25_index = None
    searchable_nodes = None

    if retriever == "ppr":
        ensure_graph_ready(
            driver,
            gds,
            relationship_types=ablation.relationship_types,
            orientation=ablation.orientation,
            apply_idf=ablation.apply_idf,
        )
        # Pre-build BM25 index once per group to speed up retrieval
        bm25_index, searchable_nodes = prepare_bm25_index(driver)

    return total_nodes, repo_path, bm25_index, searchable_nodes


# ── Per-instance query ────────────────────────────────────────────────────────

def run_instance_query(
    instance: dict,
    driver,
    gds,
    total_nodes: int,
    ablation: AblationConfig,
    retriever: str,
    bm25_index: any = None,
    searchable_nodes: any = None,
) -> dict:
    """Run the retrieval query for one instance against an already-built graph.

    The graph must already be set up (setup_group() called).
    Does NOT call ensure_graph_ready() — that is done once in setup_group().

    Returns a per-instance result dict suitable for JSONL output.
    """
    instance_id = instance["instance_id"]
    problem_statement = instance["problem_statement"]
    patch = instance.get("patch", "")
    gold_files = extract_gold_files(patch)

    t0 = time.monotonic()

    try:
        if retriever == "ppr":
            auto_entities = extract_entity_names(problem_statement)

            seeds = extract_seeds(
                driver,
                task_description=problem_statement,
                mentioned_entities=auto_entities or None,
                bm25_index=bm25_index,
                searchable_nodes=searchable_nodes,
            )

            n_seeds = len(seeds.seeds)
            if not seeds.seeds:
                logger.warning("No seeds found for %s", instance_id)
                elapsed = time.monotonic() - t0
                return _zero_result(instance_id, instance["repo"], gold_files, total_nodes, elapsed)

            ppr_results = run_ppr_from_node_ids(gds, driver, seeds.seeds, ablation.ppr_config)

            # Structural neighborhood expansion (SpIDER-inspired, enabled by default)
            if ablation.expand_neighbors and ppr_results:
                ppr_results = expand_structural_neighbors(
                    driver, ppr_results, problem_statement,
                    bm25_index=bm25_index, searchable_nodes=searchable_nodes,
                )
                ppr_results = apply_directory_colocation_bonus(ppr_results)

            # predicted_files = ALL top-k PPR results ranked by score, deduplicated by file.
            predicted_files = list(dict.fromkeys(
                r.file_path for r in ppr_results if r.file_path
            ))
        else:
            from evaluation.baselines import BM25Baseline, OneHopBaseline, RandomBaseline

            n_seeds = 0
            baseline_k = 300  # large k so recall@10 has enough candidates
            if retriever == "random":
                predicted_files = RandomBaseline().run(driver, problem_statement, k=baseline_k)
            elif retriever == "bm25":
                predicted_files = BM25Baseline().run(driver, problem_statement, k=baseline_k)
            elif retriever == "one_hop":
                predicted_files = OneHopBaseline().run(driver, problem_statement, k=baseline_k)
            else:
                raise ValueError(f"Unknown retriever: {retriever!r}")

        elapsed = time.monotonic() - t0
        r5 = recall_at_k(gold_files, predicted_files, k=5)
        r10 = recall_at_k(gold_files, predicted_files, k=10)
        mrr_val = mrr(gold_files, predicted_files)

        return {
            "instance_id": instance_id,
            "repo": instance["repo"],
            "gold_files": gold_files,
            "predicted_files": predicted_files,
            "recall_at_5": r5,
            "recall_at_10": r10,
            "mrr": mrr_val,
            "n_seeds": n_seeds,
            "total_nodes": total_nodes,
            "elapsed_seconds": round(elapsed, 2),
            "error": None,
        }

    except Exception as exc:
        elapsed = time.monotonic() - t0
        logger.error("Instance %s failed: %s", instance_id, exc, exc_info=True)
        return _zero_result(instance_id, instance.get("repo", ""), gold_files, total_nodes, elapsed, str(exc))


# ── Original per-instance entry point (used in --no-grouping mode) ────────────

def run_instance(
    instance: dict,
    driver,
    gds,
    parser,
    cache_dir: str,
    ablation: AblationConfig,
    retriever: str = "ppr",
) -> dict:
    """Run the full pipeline (setup + query) for a single SWE-bench instance.

    Thin wrapper around setup_group() + run_instance_query() used when
    grouping is disabled (--no-grouping).

    Returns a per-instance result dict suitable for JSONL output.

    Note: predicted_files is derived from ALL top-k results (not the
    token-budgeted format_context output). This is correct for evaluation:
    recall@k measures whether the gold file appears in the top-k ranked
    results, regardless of token size.
    """
    instance_id = instance["instance_id"]
    patch = instance.get("patch", "")
    gold_files = extract_gold_files(patch)

    t0 = time.monotonic()

    try:
        group_key: GroupKey = (instance["repo"], instance["base_commit"])
        total_nodes, _repo_path, bm25_index, searchable_nodes = setup_group(
            group_key, driver, gds, parser, cache_dir, ablation, retriever
        )
    except Exception as exc:
        elapsed = time.monotonic() - t0
        logger.error("Setup failed for %s: %s", instance_id, exc, exc_info=True)
        return _zero_result(instance_id, instance.get("repo", ""), gold_files, 0, elapsed, str(exc))

    return run_instance_query(
        instance, driver, gds, total_nodes, ablation, retriever, bm25_index, searchable_nodes
    )


def _zero_result(
    instance_id: str,
    repo: str,
    gold_files: list[str],
    total_nodes: int,
    elapsed: float,
    error: str | None = None,
) -> dict:
    """Return a zero-recall result dict (used for failures and empty-seed cases)."""
    return {
        "instance_id": instance_id,
        "repo": repo,
        "gold_files": gold_files,
        "predicted_files": [],
        "recall_at_5": 0.0,
        "recall_at_10": 0.0,
        "mrr": 0.0,
        "n_seeds": 0,
        "total_nodes": total_nodes,
        "elapsed_seconds": round(elapsed, 2),
        "error": error,
    }


def _remove_errored_lines(jsonl_path: Path, errored_ids: set[str]) -> None:
    """Rewrite the JSONL file, dropping lines for instances in errored_ids."""
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    kept = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            if json.loads(line)["instance_id"] not in errored_ids:
                kept.append(line)
        except (json.JSONDecodeError, KeyError):
            kept.append(line)
    jsonl_path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")


# ── Grouped runner ────────────────────────────────────────────────────────────

def _run_grouped(
    pending: list[dict],
    all_instances: list[dict],
    driver,
    gds,
    parser,
    args,
    ablation: AblationConfig,
    fh,
) -> dict:
    """Run pending instances grouped by (repo, base_commit).

    Setup (clone/parse/build/project) is performed once per group; the cheap
    query step is run once per instance.  Results are written to fh in the
    original dataset order.

    Returns a diagnostics dict with grouping statistics.
    """
    # Build instance_id → original dataset index mapping.
    id_to_idx: dict[str, int] = {inst["instance_id"]: i for i, inst in enumerate(all_instances)}

    indexed_pending = [(id_to_idx[inst["instance_id"]], inst) for inst in pending]
    groups = _group_instances(indexed_pending)

    n_groups = len(groups)
    group_sizes = [len(g.instances) for g in groups]
    mean_size = sum(group_sizes) / n_groups if n_groups else 0.0
    max_size = max(group_sizes) if group_sizes else 0
    logger.info(
        "Grouped %d pending into %d groups (mean %.1f, max %d)",
        len(pending), n_groups, mean_size, max_size,
    )

    failure_streak_threshold = getattr(args, "failure_streak_threshold", 5)

    results_buffer: dict[int, dict] = {}
    next_flush_idx = min(i for i, _ in indexed_pending) if indexed_pending else 0
    consecutive_setup_failures = 0

    for g_idx, group in enumerate(groups, start=1):
        repo, base_commit = group.key
        logger.info(
            "[group %d/%d] %s @ %.8s (%d instance(s))",
            g_idx, n_groups, repo, base_commit, len(group.instances),
        )

        try:
            total_nodes, _repo_path, bm25_index, searchable_nodes = setup_group(
                group.key, driver, gds, parser, args.cache_dir, ablation, args.retriever
            )
            consecutive_setup_failures = 0
        except Exception as exc:
            consecutive_setup_failures += 1
            logger.error(
                "Group setup failed (%s @ %s): %s — marking %d instance(s) as errors",
                repo, base_commit, exc, len(group.instances), exc_info=True,
            )
            for idx, inst in group.instances:
                patch = inst.get("patch", "")
                gold_files = extract_gold_files(patch)
                results_buffer[idx] = _zero_result(
                    inst["instance_id"], inst.get("repo", ""), gold_files, 0, 0.0, str(exc)
                )
            next_flush_idx = _flush_ordered(results_buffer, next_flush_idx, fh)

            if consecutive_setup_failures >= failure_streak_threshold:
                logger.error(
                    "Aborting: %d consecutive group setup failures (threshold=%d)",
                    consecutive_setup_failures, failure_streak_threshold,
                )
                break
            continue

        for i_idx, (idx, inst) in enumerate(group.instances, start=1):
            logger.info(
                "  [%d/%d] %s", i_idx, len(group.instances), inst["instance_id"]
            )
            result = run_instance_query(
                inst, driver, gds, total_nodes, ablation, args.retriever, bm25_index, searchable_nodes
            )
            results_buffer[idx] = result

        next_flush_idx = _flush_ordered(results_buffer, next_flush_idx, fh)

    # Flush any remaining buffered results (can happen after circuit breaker).
    if results_buffer:
        _flush_ordered(results_buffer, next_flush_idx, fh, force_all=True)

    return {
        "strategy": "repo_commit",
        "n_groups": n_groups,
        "mean_group_size": round(mean_size, 2),
        "max_group_size": max_size,
    }


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    """CLI entry point for the benchmark runner."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Run CodeGraph on SWE-bench Lite")
    parser.add_argument("--cache-dir", default=".codegraph_cache/repos", help="Repo clone cache")
    parser.add_argument("--output", default="evaluation/results/run_001", help="Output directory")
    parser.add_argument("--limit", type=int, default=0, help="Max instances (0 = all)")
    parser.add_argument("--ablation", default="baseline", help="AblationConfig name to use")
    parser.add_argument("--config", default="config.yaml", help="Path to codegraph config.yaml")
    parser.add_argument("--resume", action="store_true", help="Resume a previous run (skip completed instances)")
    parser.add_argument("--retry-errors", action="store_true", help="With --resume, re-run instances that previously errored")
    parser.add_argument(
        "--retriever",
        choices=["ppr", "random", "bm25", "one_hop"],
        default="ppr",
        help="Retrieval strategy to use (default: ppr)",
    )
    parser.add_argument(
        "--grouping",
        choices=["repo_commit", "none"],
        default="repo_commit",
        help="Grouping strategy: repo_commit (default) or none",
    )
    parser.add_argument(
        "--no-grouping",
        action="store_true",
        help="Disable grouping (alias for --grouping none)",
    )
    parser.add_argument(
        "--failure-streak-threshold",
        type=int,
        default=5,
        help="Abort grouped run after this many consecutive group setup failures (default: 5)",
    )
    args = parser.parse_args()

    # --no-grouping overrides --grouping
    if args.no_grouping:
        args.grouping = "none"

    # Select ablation config
    ablation_map = {a.name: a for a in ABLATIONS}
    if args.ablation not in ablation_map:
        raise SystemExit(f"Unknown ablation '{args.ablation}'. Options: {list(ablation_map)}")
    ablation = ablation_map[args.ablation]

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    neo4j_config = load_config(args.config)
    driver = create_driver(neo4j_config)
    gds = create_gds_client(driver)
    file_parser = create_parser()

    try:
        instances = _load_dataset()
        if args.limit > 0:
            instances = instances[: args.limit]

        per_instance_path = output_dir / "per_instance.jsonl"

        # Resume: collect already-completed instance IDs and skip them.
        completed_ids: set[str] = set()
        errored_ids: set[str] = set()
        if args.resume and per_instance_path.exists():
            with open(per_instance_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            rec = json.loads(line)
                            iid = rec["instance_id"]
                            if rec.get("error"):
                                errored_ids.add(iid)
                            else:
                                completed_ids.add(iid)
                        except (json.JSONDecodeError, KeyError):
                            pass
            # With --retry-errors, re-run errored instances (remove them from JSONL first).
            if args.retry_errors and errored_ids:
                _remove_errored_lines(per_instance_path, errored_ids)
                logger.info("Retrying %d errored instances", len(errored_ids))
            else:
                completed_ids |= errored_ids
            logger.info(
                "Resuming: skipping %d already-completed instances (%d errored)",
                len(completed_ids), len(errored_ids),
            )

        pending = [inst for inst in instances if inst["instance_id"] not in completed_ids]
        logger.info(
            "Running %d instances with ablation '%s', retriever '%s', grouping '%s'",
            len(pending),
            ablation.name,
            args.retriever,
            args.grouping,
        )

        grouping_diagnostics: dict | None = None
        write_mode = "a" if args.resume and completed_ids else "w"
        with open(per_instance_path, write_mode, encoding="utf-8") as fh:
            if args.grouping == "repo_commit":
                grouping_diagnostics = _run_grouped(
                    pending,
                    instances,
                    driver,
                    gds,
                    file_parser,
                    args,
                    ablation,
                    fh,
                )
            else:
                # --no-grouping: process each instance independently.
                for i, inst in enumerate(pending, start=1):
                    logger.info("[%d/%d] %s", i, len(pending), inst["instance_id"])
                    result = run_instance(
                        inst, driver, gds, file_parser, args.cache_dir, ablation, args.retriever
                    )
                    fh.write(json.dumps(result) + "\n")
                    fh.flush()

        # Re-read full JSONL (completed + new) for summary.
        all_results: list[dict] = []
        with open(per_instance_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        all_results.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        summary = aggregate_metrics(all_results)
        summary["ablation"] = ablation.name
        summary["retriever"] = args.retriever

        if grouping_diagnostics is not None:
            summary["grouping"] = grouping_diagnostics
        else:
            summary["grouping"] = {"strategy": "none"}

        summary_path = output_dir / "summary.json"
        summary_path.write_text(json.dumps(summary, indent=2))

        logger.info(
            "Done. Recall@10=%.3f, MRR=%.3f. Results in %s",
            summary["mean_recall_at_10"],
            summary["mean_mrr"],
            output_dir,
        )
    finally:
        driver.close()


if __name__ == "__main__":
    main()
