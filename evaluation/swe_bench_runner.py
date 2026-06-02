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
import time
from pathlib import Path
from typing import Any, TextIO

from codegraph.core.graph.graph_builder import build_graph, clear_database
from codegraph.core.graph.ppr import create_gds_client, drop_projection, run_ppr_from_node_ids
from codegraph.core.graph.connection import create_driver, load_config
from codegraph.core.parser.python_parser import create_parser, parse_directory
from codegraph.core.retrieval.pipeline import ensure_graph_ready
from codegraph.core.retrieval.seed_selection import extract_entity_names, extract_seeds, prepare_bm25_index

from evaluation.ablations import ABLATIONS, AblationConfig
from evaluation.benchmark_writer import ReportWriter, flush_ordered
from evaluation.dataset import DatasetManager, GroupKey, group_instances
from evaluation.gold_patch_parser import extract_gold_files
from evaluation.metrics import mrr, recall_at_k
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
        parser: Any,
        cache_dir: str,
        ablation: AblationConfig,
        retriever: str = "ppr",
    ) -> None:
        self.driver = driver
        self.gds = gds
        self.parser = parser
        self.cache_dir = cache_dir
        self.ablation = ablation
        self.retriever = retriever

    def setup_group(self, group_key: GroupKey) -> tuple[int, str, Any, Any]:
        """Clone, checkout, parse, and build the graph for one (repo, commit) group."""
        repo, base_commit = group_key
        repo_url = f"https://github.com/{repo}"

        drop_projection(self.gds)
        repo_path = clone_or_cache(repo_url, self.cache_dir)
        checkout_commit(repo_path, base_commit)

        entities = parse_directory(
            repo_path, self.parser, exclude_patterns=["tests", ".git"]
        )

        clear_database(self.driver)
        self._verify_db_empty()
        counts = build_graph(self.driver, entities)
        total_nodes = sum(counts.values())

        bm25_index = None
        searchable_nodes = None
        if self.retriever == "ppr":
            ensure_graph_ready(
                self.driver,
                self.gds,
                relationship_types=self.ablation.relationship_types,
                orientation=self.ablation.orientation,
                apply_idf=self.ablation.apply_idf,
            )
            bm25_index, searchable_nodes = prepare_bm25_index(self.driver)

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
                self.parser,
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
                    self.parser,
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
        auto_entities = extract_entity_names(problem_statement)
        seeds = extract_seeds(
            self.driver,
            task_description=problem_statement,
            mentioned_entities=auto_entities or None,
            bm25_index=bm25_index,
            searchable_nodes=searchable_nodes,
        )
        n_seeds = len(seeds.seeds)
        seed_node_ids = list(seeds.seeds.keys())
        seed_files = self._fetch_node_file_paths(seed_node_ids)

        if not seeds.seeds:
            logger.warning("No seeds found for %s", instance_id)
            elapsed = time.monotonic() - t0
            return zero_result(instance_id, repo, gold_files, total_nodes, elapsed)

        ppr_results = run_ppr_from_node_ids(
            self.gds, self.driver, seeds.seeds, self.ablation.ppr_config
        )
        predicted_files = list(dict.fromkeys(
            r.file_path for r in ppr_results if r.file_path
        ))
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
    parser: Any,
    cache_dir: str,
    ablation: AblationConfig,
    retriever: str,
) -> tuple[int, str, Any, Any]:
    """Module-level wrapper around BenchmarkRunner.setup_group."""
    runner = BenchmarkRunner(driver, gds, parser, cache_dir, ablation, retriever)
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
    parser: Any,
    cache_dir: str,
    ablation: AblationConfig,
    retriever: str = "ppr",
) -> dict:
    """Module-level wrapper around BenchmarkRunner.run_instance."""
    runner = BenchmarkRunner(driver, gds, parser, cache_dir, ablation, retriever)
    return runner.run_instance(instance)


def _run_grouped(
    pending: list[dict],
    all_instances: list[dict],
    completed_ids: set[str] | None,
    driver: Any,
    gds: Any,
    parser: Any,
    args: Any,
    ablation: AblationConfig,
    fh: TextIO,
) -> dict:
    """Module-level wrapper around BenchmarkRunner.run_grouped."""
    runner = BenchmarkRunner(
        driver, gds, parser, args.cache_dir, ablation, args.retriever
    )
    return runner.run_grouped(
        pending,
        all_instances,
        fh,
        failure_streak_threshold=getattr(args, "failure_streak_threshold", 5),
    )


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.getLogger("evaluation").setLevel(logging.INFO)
    logging.getLogger("codegraph").setLevel(logging.INFO)


def main() -> None:
    """CLI entry point for the benchmark runner."""
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    os.environ["HUGGINGFACE_HUB_VERBOSITY"] = "error"
    _configure_logging()

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
    args = parser.parse_args()

    if args.no_grouping:
        args.grouping = "none"

    ablation_map = {a.name: a for a in ABLATIONS}
    if args.ablation not in ablation_map:
        raise SystemExit(f"Unknown ablation '{args.ablation}'. Options: {list(ablation_map)}")
    ablation = ablation_map[args.ablation]

    writer = ReportWriter(Path(args.output))
    neo4j_config = load_config(args.config)
    driver = create_driver(neo4j_config)
    gds = create_gds_client(driver)
    file_parser = create_parser()

    try:
        instances = DatasetManager().load_limited(limit=args.limit)
        completed_ids, errored_ids = writer.load_resume_state(
            args.resume, args.retry_errors
        )
        if args.retry_errors and errored_ids:
            logger.info("Retrying %d errored instances", len(errored_ids))

        pending = [i for i in instances if i["instance_id"] not in completed_ids]
        logger.info(
            "Running %d instances with ablation '%s', retriever '%s', grouping '%s'",
            len(pending), ablation.name, args.retriever, args.grouping,
        )

        runner = BenchmarkRunner(
            driver, gds, file_parser, args.cache_dir, ablation, args.retriever
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

        grouping = grouping_diagnostics or {"strategy": "none"}
        all_results = writer.read_all_results()
        summary = writer.write_summary(
            all_results, ablation.name, args.retriever, grouping
        )
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
