"""Diagnostic: show seeds + PPR ranking for instance 1 of the pilot."""

import sys
sys.path.insert(0, "src")

from codegraph.core.graph.connection import load_config, create_driver
from codegraph.core.graph.ppr import create_gds_client, run_ppr_from_node_ids, PPRConfig
from codegraph.core.retrieval.seed_selection import extract_seeds, extract_entity_names
from codegraph.core.retrieval.pipeline import ensure_graph_ready

# The graph from the last pilot run is still in Neo4j (astropy @ d16bfe05)
cfg = load_config("config.yaml")
d = create_driver(cfg)
gds = create_gds_client(d)

PROBLEM = (
    "Modeling's `separability_matrix` does not compute separability correctly "
    "for nested CompoundModels"
)
GOLD = "astropy/modeling/separable.py"

print(f"Problem: {PROBLEM[:80]}...")
print(f"Gold file: {GOLD}")
print()

entities = extract_entity_names(PROBLEM)
print(f"Extracted entity names: {entities}")

seeds = extract_seeds(d, task_description=PROBLEM, mentioned_entities=entities)
print(f"Seeds found: {len(seeds.seeds)} nodes")

with d.session() as s:
    for nid, w in sorted(seeds.seeds.items(), key=lambda x: -x[1]):
        r = s.run(
            "MATCH (n) WHERE id(n) = $nid "
            "RETURN n.qualified_name AS qn, n.file_path AS fp, labels(n)[0] AS lbl",
            nid=nid,
        )
        rec = r.single()
        if rec:
            print(f"  seed w={w:.3f} [{rec['lbl']}] {rec['qn'][:60]}")

print()

# Check if separability_matrix exists in graph
with d.session() as s:
    r = s.run(
        "MATCH (n) WHERE n.name = 'separability_matrix' "
        "RETURN n.qualified_name AS qn, n.file_path AS fp, labels(n)[0] AS lbl"
    )
    found = list(r)
    print(f"'separability_matrix' in graph: {len(found)} matches")
    for rec in found:
        print(f"  [{rec['lbl']}] {rec['qn']} in {rec['fp']}")

print()

# Run PPR and show top-20 results with file paths
ensure_graph_ready(d, gds)
ppr_results = run_ppr_from_node_ids(gds, d, seeds.seeds, PPRConfig(top_k=20))

print(f"PPR top-20 results (gold = {GOLD}):")
gold_found = False
for i, r in enumerate(ppr_results, 1):
    marker = " *** GOLD ***" if r.file_path == GOLD else ""
    if r.file_path == GOLD:
        gold_found = True
    print(f"  [{i:2d}] score={r.score:.6f} [{r.label}] {r.file_path}{marker}")

if not gold_found:
    print(f"\n  Gold file NOT in top-20 PPR results!")

# Also show ranked file list (deduplicated)
ranked_files = list(dict.fromkeys(r.file_path for r in ppr_results if r.file_path))
print(f"\nRanked unique files:")
for i, fp in enumerate(ranked_files, 1):
    marker = " *** GOLD ***" if fp == GOLD else ""
    print(f"  [{i}] {fp}{marker}")

d.close()
