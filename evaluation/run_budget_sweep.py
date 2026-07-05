"""Run a token budget sensitivity sweep for CodeGraph.
Evaluates Recall@10 but enforces varying token budgets.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))

from codegraph.core.graph.connection import load_config, create_driver
from codegraph.core.graph.ppr import create_gds_client
from codegraph.core.retrieval.pipeline import run_core_retrieval
from codegraph.core.retrieval.post_processing import format_context
from evaluation.dataset import DatasetManager
from evaluation.swe_bench_runner import BenchmarkRunner, extract_gold_files, group_instances
from evaluation.ablations import ABLATIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", default=".codegraph_cache/repos")
    parser.add_argument("--output", default="evaluation/results/budget_sweep.json")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--budgets", type=int, nargs="+", default=[2000, 4000, 6000, 8000, 10000])
    args = parser.parse_args()

    # Use the optimal config
    optimal_ablation = next(a for a in ABLATIONS if a.name == "baseline")

    neo4j_config = load_config("config.yaml")
    driver = create_driver(neo4j_config)
    gds = create_gds_client(driver)

    instances = DatasetManager().load_filtered(limit=args.limit)
    if not instances:
        sys.exit("No instances found.")

    id_to_idx = {inst["instance_id"]: i for i, inst in enumerate(instances)}
    indexed = [(id_to_idx[inst["instance_id"]], inst) for inst in instances]
    groups = group_instances(indexed)

    runner = BenchmarkRunner(driver, gds, args.cache_dir, optimal_ablation, "ppr")
    
    results_by_budget = {b: {"hits": 0, "total": 0} for b in args.budgets}

    for g_idx, group in enumerate(groups, start=1):
        repo, base_commit = group.key
        logger.info(f"Group {g_idx}/{len(groups)}: {repo}@{base_commit[:8]}")
        try:
            total_nodes, repo_path, bm25_index, searchable_nodes = runner.setup_group(group.key)
        except Exception as exc:
            logger.error(f"Setup failed: {exc}")
            continue
            
        for _, inst in group.instances:
            gold_files = extract_gold_files(inst.get("patch", ""))
            
            # Run core retrieval
            core = run_core_retrieval(
                driver, gds,
                task_description=inst["problem_statement"],
                ppr_config=optimal_ablation.ppr_config,
                relationship_types=optimal_ablation.relationship_types,
                orientation=optimal_ablation.orientation,
                apply_idf=optimal_ablation.apply_idf,
                bm25_index=bm25_index,
                searchable_nodes=searchable_nodes,
                graph_ready=True
            )
            
            if core and core.ppr_results:
                # Format context at the MAXIMUM budget to see token accumulation
                max_budget = max(args.budgets)
                context_items = format_context(core.ppr_results, repo_path, max_budget)
                
                # Check hits at each budget
                for b in args.budgets:
                    results_by_budget[b]["total"] += 1
                    
                    # Accumulate files up to this budget
                    budget_files = set()
                    tokens_so_far = 0
                    for item in context_items:
                        if tokens_so_far + item.token_count > b:
                            break
                        budget_files.add(item.file_path)
                        tokens_so_far += item.token_count
                        
                    # Check if any gold file is in the budget_files
                    if any(gf in budget_files for gf in gold_files):
                        results_by_budget[b]["hits"] += 1
            else:
                for b in args.budgets:
                    results_by_budget[b]["total"] += 1

    # Print and save results
    print("\n=== Budget Sensitivity Results ===")
    out_data = {}
    for b in sorted(args.budgets):
        hits = results_by_budget[b]["hits"]
        total = results_by_budget[b]["total"]
        recall = hits / total if total > 0 else 0.0
        print(f"Budget {b:5d} tokens: Recall = {recall:.1%} ({hits}/{total})")
        out_data[b] = recall
        
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(out_data, indent=2))
    print(f"Saved to {args.output}")

if __name__ == "__main__":
    main()
