"""SWE-bench benchmark runner for CodeGraph.

Entry point:
    python -m evaluation.swe_bench_runner \\
        --cache-dir .codegraph_cache \\
        --output evaluation/results/run_001 \\
        [--limit 5]           # pilot run on first N instances
        [--ablation baseline] # which AblationConfig to use (default: baseline)
        [--grouping repo_commit|none]  # group instances by (repo, base_commit)
        [--no-grouping]       # alias for --grouping none
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, TextIO

from codegraph.core.graph.graph_builder import build_graph, clear_database
from codegraph.core.graph.ppr import create_gds_client, drop_projection
from codegraph.core.graph.connection import create_driver, load_config
from codegraph.core.parser import parse_directory
from codegraph.core.retrieval.pipeline import (
    ensure_graph_ready,
    file_paths_from_ppr_results,
    run_core_retrieval,
)
from codegraph.core.retrieval.seed_selection import prepare_bm25_index
from codegraph.utils.config import load_raw_config, parse_signal_weights

from evaluation.ablations import ABLATIONS, AblationConfig
from evaluation.benchmark_writer import ReportWriter, flush_ordered
from evaluation.dataset import DatasetManager, GroupKey, group_instances
from evaluation.instance_filter import resolve_instance_ids_arg
from evaluation.gold_patch_parser import extract_gold_files
from evaluation.metrics import mrr, recall_at_k
from evaluation.progress import BenchmarkProgress
from evaluation.repo_manager import checkout_commit, clone_or_cache

logger = logging.getLogger(__name__)

# Backward-compatible re-exports for tests
_group_instances = group_instances
_flush_ordered = flush_ordered


class BenchmarkRunner:
    """Encapsulates Neo4j/GDS/parser resources and the SWE-bench pipeline."""

    def __init__(
        self,
        driver: Any,
        gds: Any,
        cache_dir: str,
        ablation: AblationConfig,
        retriever: str = "ppr",
        signal_weights: dict[str, float] | None = None,
        exclude_seed_paths: list[str] | None = None,
        file_rank_by: str = "first_entity",
        progress: BenchmarkProgress | None = None,
    ) -> None:
        self.driver = driver
        self.gds = gds
        self.cache_dir = cache_dir
        self.ablation = ablation
        self.retriever = retriever
        self.signal_weights = signal_weights
        self.exclude_seed_paths = exclude_seed_paths or []
        self.file_rank_by = file_rank_by
        self.progress = progress

    def setup_group(self, group_key: GroupKey) -> tuple[int, str, Any, Any]:
        """Clone, checkout, parse, and build the graph for one (repo, commit) group."""
        repo, base_commit = group_key
        repo_url = f"https://github.com/{repo}"
        label = f"{repo}@{base_commit[:8]}"

        if self.progress:
            self.progress.phase(f"{label}: drop GDS projection")
        drop_projection(self.gds)

        if self.progress:
            self.progress.phase(f"{label}: clone or cache repo")
        t0 = time.monotonic()
        repo_path = clone_or_cache(repo_url, self.cache_dir)

        if self.progress:
            self.progress.phase(f"{label}: checkout {base_commit[:12]}")
        checkout_commit(repo_path, base_commit)

        if self.progress:
            self.progress.phase(f"{label}: parse Python sources")
        entities = parse_directory(
            repo_path, exclude_patterns=["tests", ".git"]
        )

        if self.progress:
            self.progress.phase(
                f"{label}: build Neo4j graph ({len(entities)} entities)"
            )
        clear_database(self.driver)
        self._verify_db_empty()
        counts = build_graph(self.driver, entities)
        total_nodes = sum(counts.values())

        bm25_index = None
        searchable_nodes = None
        if self.retriever == "ppr":
            if self.progress:
                self.progress.phase(f"{label}: IDF + GDS projection")
            ensure_graph_ready(
                self.driver,
                self.gds,
                relationship_types=self.ablation.relationship_types,
                orientation=self.ablation.orientation,
                apply_idf=self.ablation.apply_idf,
            )
            if self.progress:
                self.progress.phase(f"{label}: BM25 index")
            bm25_index, searchable_nodes = prepare_bm25_index(
                self.driver, exclude_paths=self.exclude_seed_paths or None
            )

        if self.progress:
            setup_s = time.monotonic() - t0
            self.progress.phase(
                f"{label}: ready ({total_nodes} nodes, setup {setup_s:.0f}s)"
            )

        return total_nodes, repo_path, bm25_index, searchable_nodes

    def run_instance_query(
        self,
        instance: dict,
        total_nodes: int,
        bm25_index: Any = None,
        searchable_nodes: Any = None,
    ) -> dict:
        """Run retrieval for one instance against an already-built graph."""
        instance_id = instance["instance_id"]
        problem_statement = instance["problem_statement"]
        patch = instance.get("patch", "")
        gold_files = extract_gold_files(patch)

        t0 = time.monotonic()
        try:
            if self.retriever == "ppr":
                return self._run_ppr_query(
                    instance_id,
                    instance["repo"],
                    problem_statement,
                    gold_files,
                    total_nodes,
                    t0,
                    bm25_index,
                    searchable_nodes,
                )
            return self._run_baseline_query(
                instance_id,
                instance["repo"],
                problem_statement,
                gold_files,
                total_nodes,
                t0,
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            logger.error("Instance %s failed: %s", instance_id, exc, exc_info=True)
            return zero_result(
                instance_id, instance.get("repo", ""), gold_files, total_nodes, elapsed, str(exc)
            )

    def run_instance(self, instance: dict) -> dict:
        """Full pipeline (setup + query) for one instance (no grouping)."""
        instance_id = instance["instance_id"]
        patch = instance.get("patch", "")
        gold_files = extract_gold_files(patch)
        t0 = time.monotonic()

        try:
            group_key: GroupKey = (instance["repo"], instance["base_commit"])
            total_nodes, _, bm25_index, searchable_nodes = setup_group(
                group_key,
                self.driver,
                self.gds,
                self.cache_dir,
                self.ablation,
                self.retriever,
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            logger.error("Setup failed for %s: %s", instance_id, exc, exc_info=True)
            return zero_result(
                instance_id, instance.get("repo", ""), gold_files, 0, elapsed, str(exc)
            )

        return run_instance_query(
            instance,
            self.driver,
            self.gds,
            total_nodes,
            self.ablation,
            self.retriever,
            bm25_index,
            searchable_nodes,
        )

    def run_grouped(
        self,
        pending: list[dict],
        all_instances: list[dict],
        fh: TextIO,
        failure_streak_threshold: int = 5,
    ) -> dict:
        """Run pending instances grouped by (repo, base_commit)."""
        id_to_idx = {inst["instance_id"]: i for i, inst in enumerate(all_instances)}
        indexed_pending = [(id_to_idx[inst["instance_id"]], inst) for inst in pending]
        groups = group_instances(indexed_pending)

        n_groups = len(groups)
        group_sizes = [len(g.instances) for g in groups]
        mean_size = sum(group_sizes) / n_groups if n_groups else 0.0
        max_size = max(group_sizes) if group_sizes else 0
        logger.info(
            "Grouped %d pending into %d groups (mean %.1f, max %d)",
            len(pending), n_groups, mean_size, max_size,
        )

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
                total_nodes, _, bm25_index, searchable_nodes = setup_group(
                    group.key,
                    self.driver,
                    self.gds,
                    self.cache_dir,
                    self.ablation,
                    self.retriever,
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
                    results_buffer[idx] = zero_result(
                        inst["instance_id"], inst.get("repo", ""), gold_files, 0, 0.0, str(exc)
                    )
                    if self.progress:
                        self.progress.instance_done(
                            results_buffer[idx],
                            group_label=f"g{g_idx}/{n_groups}",
                        )
                next_flush_idx = flush_ordered(results_buffer, next_flush_idx, fh)

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
                results_buffer[idx] = run_instance_query(
                    inst,
                    self.driver,
                    self.gds,
                    total_nodes,
                    self.ablation,
                    self.retriever,
                    bm25_index,
                    searchable_nodes,
                )
                if self.progress:
                    self.progress.instance_done(
                        results_buffer[idx],
                        group_label=f"g{g_idx}/{n_groups}",
                    )

            next_flush_idx = flush_ordered(results_buffer, next_flush_idx, fh)

        if results_buffer:
            flush_ordered(results_buffer, next_flush_idx, fh, force_all=True)

        return {
            "strategy": "repo_commit",
            "n_groups": n_groups,
            "mean_group_size": round(mean_size, 2),
            "max_group_size": max_size,
        }

    def _run_ppr_query(
        self,
        instance_id: str,
        repo: str,
        problem_statement: str,
        gold_files: list[str],
        total_nodes: int,
        t0: float,
        bm25_index: Any,
        searchable_nodes: Any,
    ) -> dict:
        core = run_core_retrieval(
            self.driver,
            self.gds,
            task_description=problem_statement,
            mentioned_entities=None,
            ppr_config=self.ablation.ppr_config,
            signal_weights=self.signal_weights,
            relationship_types=self.ablation.relationship_types,
            orientation=self.ablation.orientation,
            apply_idf=self.ablation.apply_idf,
            exclude_seed_paths=self.exclude_seed_paths or None,
            bm25_index=bm25_index,
            searchable_nodes=searchable_nodes,
            graph_ready=True,
        )
        if core is None:
            logger.warning("No seeds found for %s", instance_id)
            elapsed = time.monotonic() - t0
            return zero_result(instance_id, repo, gold_files, total_nodes, elapsed)

        n_seeds = len(core.seeds.seeds)
        seed_files = self._fetch_node_file_paths(list(core.seeds.seeds.keys()))
        predicted_files = file_paths_from_ppr_results(
            core.ppr_results, rank_by=self.file_rank_by
        )
        return self._metrics_result(
            instance_id, repo, gold_files, predicted_files,
            n_seeds, seed_files, total_nodes, t0,
        )

    def _run_baseline_query(
        self,
        instance_id: str,
        repo: str,
        problem_statement: str,
        gold_files: list[str],
        total_nodes: int,
        t0: float,
    ) -> dict:
        from evaluation.baselines import BM25Baseline, OneHopBaseline, RandomBaseline

        baseline_k = 300
        if self.retriever == "random":
            predicted_files = RandomBaseline().run(self.driver, problem_statement, k=baseline_k)
        elif self.retriever == "bm25":
            predicted_files = BM25Baseline().run(self.driver, problem_statement, k=baseline_k)
        elif self.retriever == "one_hop":
            predicted_files = OneHopBaseline().run(self.driver, problem_statement, k=baseline_k)
        else:
            raise ValueError(f"Unknown retriever: {self.retriever!r}")

        return self._metrics_result(
            instance_id, repo, gold_files, predicted_files,
            0, [], total_nodes, t0,
        )

    def _metrics_result(
        self,
        instance_id: str,
        repo: str,
        gold_files: list[str],
        predicted_files: list[str],
        n_seeds: int,
        seed_files: list[str],
        total_nodes: int,
        t0: float,
    ) -> dict:
        elapsed = time.monotonic() - t0
        return {
            "instance_id": instance_id,
            "repo": repo,
            "gold_files": gold_files,
            "predicted_files": predicted_files,
            "recall_at_5": recall_at_k(gold_files, predicted_files, k=5),
            "recall_at_10": recall_at_k(gold_files, predicted_files, k=10),
            "mrr": mrr(gold_files, predicted_files),
            "n_seeds": n_seeds,
            "seed_files": seed_files,
            "total_nodes": total_nodes,
            "elapsed_seconds": round(elapsed, 2),
            "error": None,
        }

    def _verify_db_empty(self) -> None:
        with self.driver.session() as session:
            record = session.run("MATCH (n) RETURN 1 LIMIT 1").single()
            if record is not None:
                raise RuntimeError("Database not empty after clear_database()")

    def _fetch_node_file_paths(self, node_ids: list[int]) -> list[str]:
        if not node_ids:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (n)
                WHERE id(n) IN $node_ids AND n.file_path IS NOT NULL
                RETURN DISTINCT n.file_path AS file_path
                """,
                node_ids=node_ids,
            )
            return [r["file_path"] for r in result]


def zero_result(
    instance_id: str,
    repo: str,
    gold_files: list[str],
    total_nodes: int,
    elapsed: float,
    error: str | None = None,
) -> dict:
    """Return a zero-recall result dict (failures and empty-seed cases)."""
    return {
        "instance_id": instance_id,
        "repo": repo,
        "gold_files": gold_files,
        "predicted_files": [],
        "recall_at_5": 0.0,
        "recall_at_10": 0.0,
        "mrr": 0.0,
        "n_seeds": 0,
        "seed_files": [],
        "total_nodes": total_nodes,
        "elapsed_seconds": round(elapsed, 2),
        "error": error,
    }


# Backward-compatible module-level wrappers for tests and external callers
def setup_group(
    group_key: GroupKey,
    driver: Any,
    gds: Any,
    cache_dir: str,
    ablation: AblationConfig,
    retriever: str,
) -> tuple[int, str, Any, Any]:
    """Module-level wrapper around BenchmarkRunner.setup_group."""
    runner = BenchmarkRunner(driver, gds, cache_dir, ablation, retriever)
    return runner.setup_group(group_key)


def run_instance_query(
    instance: dict,
    driver: Any,
    gds: Any,
    total_nodes: int,
    ablation: AblationConfig,
    retriever: str,
    bm25_index: Any = None,
    searchable_nodes: Any = None,
) -> dict:
    """Module-level wrapper around BenchmarkRunner.run_instance_query."""
    runner = BenchmarkRunner(driver, gds, None, "", ablation, retriever)
    runner.driver = driver
    runner.gds = gds
    return runner.run_instance_query(
        instance, total_nodes, bm25_index, searchable_nodes
    )


def run_instance(
    instance: dict,
    driver: Any,
    gds: Any,
    cache_dir: str,
    ablation: AblationConfig,
    retriever: str = "ppr",
) -> dict:
    """Module-level wrapper around BenchmarkRunner.run_instance."""
    runner = BenchmarkRunner(driver, gds, cache_dir, ablation, retriever)
    return runner.run_instance(instance)


def _run_grouped(
    pending: list[dict],
    all_instances: list[dict],
    completed_ids: set[str] | None,
    driver: Any,
    gds: Any,
    args: Any,
    ablation: AblationConfig,
    fh: TextIO,
) -> dict:
    """Module-level wrapper around BenchmarkRunner.run_grouped."""
    runner = BenchmarkRunner(
        driver, gds, args.cache_dir, ablation, args.retriever
    )
    return runner.run_grouped(
        pending,
        all_instances,
        fh,
        failure_streak_threshold=getattr(args, "failure_streak_threshold", 5),
    )


def _git_commit_hash() -> str | None:
    """Return current git HEAD sha for reproducibility metadata."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return out.stdout.strip() or None
    except (subprocess.SubprocessError, OSError):
        return None


def _load_benchmark_seed_config(config_path: str) -> tuple[dict[str, float], list[str]]:
    """Load seed_selection settings from config.yaml (same as MCP/CLI)."""
    raw = load_raw_config(config_path)
    seed_section = raw.get("seed_selection") or {}
    weights = parse_signal_weights(seed_section)
    exclude = seed_section.get("exclude_seed_paths") or []
    return weights, list(exclude)


def _load_compare_baseline(path: str | None) -> dict | None:
    """Load a reference summary.json for delta reporting."""
    if not path:
        return None
    ref = Path(path)
    if not ref.exists():
        return None
    baseline = json.loads(ref.read_text(encoding="utf-8"))
    return {
        "path": str(ref),
        "mean_recall_at_10": baseline.get("mean_recall_at_10"),
        "instances_with_zero_recall": baseline.get("instances_with_zero_recall"),
        "n_instances": baseline.get("n_instances"),
    }


def _configure_logging(*, verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("evaluation").setLevel(logging.DEBUG if verbose else logging.INFO)
    logging.getLogger("codegraph").setLevel(logging.DEBUG if verbose else logging.INFO)


def _preflight_neo4j(config_path: str) -> None:
    """Fail fast with a clear message if Neo4j is unreachable."""
    from codegraph.core.graph.connection import verify_connectivity

    cfg = load_config(config_path)
    driver = create_driver(cfg)
    try:
        verify_connectivity(driver)
    except Exception as exc:
        raise SystemExit(
            "Neo4j is not reachable. Start Neo4j + GDS, set NEO4J_PASSWORD, "
            f"then run `codegraph doctor`. Details: {exc}"
        ) from exc
    finally:
        driver.close()


def main() -> None:
    """CLI entry point for the benchmark runner."""
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    os.environ["HUGGINGFACE_HUB_VERBOSITY"] = "error"
    os.environ.setdefault("PYTHONUNBUFFERED", "1")

    parser = argparse.ArgumentParser(description="Run CodeGraph on SWE-bench Lite")
    parser.add_argument("--cache-dir", default=".codegraph_cache/repos")
    parser.add_argument("--output", default="evaluation/results/run_001")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--ablation", default="baseline")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument(
        "--retriever",
        choices=["ppr", "random", "bm25", "one_hop"],
        default="ppr",
    )
    parser.add_argument(
        "--grouping",
        choices=["repo_commit", "none"],
        default="repo_commit",
    )
    parser.add_argument("--no-grouping", action="store_true")
    parser.add_argument("--failure-streak-threshold", type=int, default=5)
    parser.add_argument(
        "--file-rank-by",
        choices=["first_entity", "max_score"],
        default="first_entity",
        help="How to rank files from PPR entity hits (default: first_entity)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging for codegraph and evaluation",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip Neo4j connectivity check at startup",
    )
    parser.add_argument(
        "--instance-ids-file",
        default=None,
        help="JSON list of instance_ids or file.json:tier_key subset",
    )
    parser.add_argument(
        "--repo-prefix",
        default=None,
        help="Only instances whose repo field contains this prefix",
    )
    parser.add_argument(
        "--subset-name",
        default=None,
        help="Label stored in summary.json (default: tier key or file stem)",
    )
    parser.add_argument(
        "--compare-baseline",
        default=None,
        help="Path to reference summary.json for comparison metadata",
    )
    args = parser.parse_args()
    Path(args.output).mkdir(parents=True, exist_ok=True)
    _configure_logging(verbose=args.verbose)

    if args.no_grouping:
        args.grouping = "none"

    ablation_map = {a.name: a for a in ABLATIONS}
    if args.ablation not in ablation_map:
        raise SystemExit(f"Unknown ablation '{args.ablation}'. Options: {list(ablation_map)}")
    ablation = ablation_map[args.ablation]

    writer = ReportWriter(Path(args.output))
    progress = BenchmarkProgress(writer.output_dir, total_instances=0)

    if not args.skip_preflight:
        progress.emit("Checking Neo4j connectivity …")
        _preflight_neo4j(args.config)
        progress.emit("Neo4j OK")

    neo4j_config = load_config(args.config)
    signal_weights, exclude_seed_paths = _load_benchmark_seed_config(args.config)
    driver = create_driver(neo4j_config)
    gds = create_gds_client(driver)
    instance_ids: set[str] | None = None
    subset_name = args.subset_name
    if args.instance_ids_file:
        instance_ids, tier_label = resolve_instance_ids_arg(args.instance_ids_file)
        subset_name = subset_name or tier_label

    try:
        instances = DatasetManager().load_filtered(
            limit=args.limit,
            instance_ids=instance_ids,
            repo_prefix=args.repo_prefix,
        )
        if instance_ids:
            missing = instance_ids - {i["instance_id"] for i in instances}
            if missing:
                logger.warning(
                    "%d instance id(s) not in dataset: %s",
                    len(missing),
                    sorted(missing)[:5],
                )
        if not instances:
            raise SystemExit("No instances matched filters.")
        completed_ids, errored_ids = writer.load_resume_state(
            args.resume, args.retry_errors
        )
        if args.retry_errors and errored_ids:
            logger.info("Retrying %d errored instances", len(errored_ids))

        pending = [i for i in instances if i["instance_id"] not in completed_ids]
        progress.total_instances = len(pending)
        progress._write_snapshot()
        subset_note = f", subset={subset_name}" if subset_name else ""
        progress.emit(
            f"Run started: {len(pending)} instances, ablation={ablation.name}, "
            f"retriever={args.retriever}{subset_note}, output={writer.output_dir}"
        )
        logger.info(
            "Running %d instances with ablation '%s', retriever '%s', grouping '%s'",
            len(pending), ablation.name, args.retriever, args.grouping,
        )

        runner = BenchmarkRunner(
            driver,
            gds,
            args.cache_dir,
            ablation,
            args.retriever,
            signal_weights=signal_weights or None,
            exclude_seed_paths=exclude_seed_paths,
            file_rank_by=args.file_rank_by,
            progress=progress,
        )
        grouping_diagnostics: dict | None = None
        append = args.resume and bool(completed_ids)

        with writer.open_jsonl(append) as fh:
            if args.grouping == "repo_commit":
                grouping_diagnostics = runner.run_grouped(pending, instances, fh)
            else:
                for i, inst in enumerate(pending, start=1):
                    logger.info("[%d/%d] %s", i, len(pending), inst["instance_id"])
                    result = runner.run_instance(inst)
                    fh.write(json.dumps(result) + "\n")
                    fh.flush()
                    progress.instance_done(result)

        grouping = grouping_diagnostics or {"strategy": "none"}
        all_results = writer.read_all_results()
        summary = writer.write_summary(
            all_results,
            ablation.name,
            args.retriever,
            grouping,
            git_commit=_git_commit_hash(),
            subset_name=subset_name,
            compare_baseline=_load_compare_baseline(args.compare_baseline),
        )
        progress.finish(summary)
        logger.info(
            "Done. Recall@10=%.3f, MRR=%.3f. Results in %s",
            summary["mean_recall_at_10"],
            summary["mean_mrr"],
            writer.output_dir,
        )
    finally:
        driver.close()


if __name__ == "__main__":
    main()
