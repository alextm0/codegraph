"""Demo: CodeGraph retrieval on psf/requests v2.31.0.

Run this after indexing the requests repo:
    codegraph --config demo/config.yaml rebuild

Then execute:
    python demo/requests_demo.py
"""

import os
import sys
from pathlib import Path

# Ensure codegraph is importable when run from the project root.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from neo4j import GraphDatabase
from graphdatascience import GraphDataScience

from codegraph.core.retrieval.pipeline import run_retrieval_pipeline
from codegraph.core.retrieval.seed_selection import prepare_bm25_index
from codegraph.core.graph.ppr import PPRConfig, create_gds_client

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "password")

REQUESTS_ROOT = str(Path(__file__).parent / "requests" / "requests")

# Curated demo queries with expected gold files (for manual verification).
DEMO_QUERIES: list[dict] = [
    {
        "task": "how does session cookie handling work",
        "gold_files": ["sessions.py", "cookies.py"],
        "entities": [],
    },
    {
        "task": "how are HTTP redirects followed and resolved",
        "gold_files": ["sessions.py", "models.py"],
        "entities": [],
    },
    {
        "task": "how does proxy authentication work",
        "gold_files": ["auth.py", "adapters.py"],
        "entities": [],
    },
    {
        "task": "how is SSL certificate verification done",
        "gold_files": ["adapters.py", "utils.py"],
        "entities": [],
    },
]

PPR_CONFIG = PPRConfig(damping_factor=0.70, top_k=30)
EXCLUDE_SEED_PATHS = ["tests/", "test_"]


def _short_path(file_path: str) -> str:
    """Return the filename only for display."""
    return Path(file_path).name


def _recall_at_k(top_files: list[str], gold_files: list[str], k: int) -> float:
    """Fraction of gold_files appearing in the top-k retrieved files."""
    top_k_names = {_short_path(f) for f in top_files[:k]}
    hits = sum(1 for g in gold_files if g in top_k_names)
    return hits / len(gold_files) if gold_files else 0.0


def run_demo(driver, gds: GraphDataScience) -> None:
    """Run all demo queries and print a comparison table."""
    print("\n" + "=" * 70)
    print(" CodeGraph Demo — psf/requests v2.31.0")
    print("=" * 70)

    # Pre-build BM25 index (excluding test files from seed candidates).
    bm25_index, searchable_nodes = prepare_bm25_index(
        driver, exclude_paths=EXCLUDE_SEED_PATHS
    )
    if bm25_index is None:
        print("ERROR: No nodes in graph. Run: codegraph --config demo/config.yaml rebuild")
        return

    total_r10 = 0.0

    for i, query in enumerate(DEMO_QUERIES, 1):
        task = query["task"]
        gold = query["gold_files"]
        entities = query["entities"] or None

        print(f"\n[{i}/{len(DEMO_QUERIES)}] Query: \"{task}\"")
        print(f"  Expected: {gold}")

        results = run_retrieval_pipeline(
            driver=driver,
            gds=gds,
            task_description=task,
            project_root=REQUESTS_ROOT,
            mentioned_entities=entities,
            ppr_config=PPR_CONFIG,
            token_budget=8000,
            exclude_seed_paths=EXCLUDE_SEED_PATHS,
        )

        # Collect unique files in PPR rank order.
        seen: set[str] = set()
        ranked_files: list[str] = []
        for r in results:
            if r.file_path not in seen:
                seen.add(r.file_path)
                ranked_files.append(r.file_path)

        print("  Top-5 files (CodeGraph):")
        for rank, fp in enumerate(ranked_files[:5], 1):
            name = _short_path(fp)
            hit = "✓" if name in gold else " "
            print(f"    [{hit}] #{rank}  {name}")

        r10 = _recall_at_k(ranked_files, gold, k=10)
        total_r10 += r10
        print(f"  Recall@10: {r10:.0%}")

    avg = total_r10 / len(DEMO_QUERIES)
    print(f"\n{'=' * 70}")
    print(f"  Average Recall@10 across {len(DEMO_QUERIES)} queries: {avg:.0%}")
    print("=" * 70 + "\n")


def main() -> None:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
    try:
        driver.verify_connectivity()
    except Exception as e:
        print(f"ERROR: Cannot connect to Neo4j at {NEO4J_URI}: {e}")
        sys.exit(1)

    gds = create_gds_client(driver)
    try:
        run_demo(driver, gds)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
