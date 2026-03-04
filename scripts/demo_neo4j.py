"""Educational end-to-end demo: tree-sitter parsing -> Neo4j graph -> PPR.

Run with:
    python -m scripts.demo_neo4j

Requires Neo4j running at bolt://localhost:7687 with credentials neo4j/password.
"""

import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup logging so the demo prints INFO messages to stdout
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("demo_neo4j")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
USER_AUTH = REPO_ROOT / "tests" / "fixtures" / "user_auth"


def main() -> None:
    # -----------------------------------------------------------------------
    # Step 1: Parse the user_auth fixture with tree-sitter
    # -----------------------------------------------------------------------
    logger.info("=== Step 1: Parse user_auth fixture with tree-sitter ===")

    from src.parser.python_parser import create_parser, parse_directory

    parser = create_parser()
    all_entities = parse_directory(str(USER_AUTH), parser)

    logger.info("Parsed %d files", len(all_entities))
    for fe in all_entities:
        logger.info(
            "  %s  | funcs=%d  classes=%d  methods=%d  imports=%d  calls=%d",
            fe.file_path,
            len(fe.functions),
            len(fe.classes),
            len(fe.methods),
            len(fe.imports),
            len(fe.calls),
        )

    # -----------------------------------------------------------------------
    # Step 2: Connect to Neo4j
    # -----------------------------------------------------------------------
    logger.info("")
    logger.info("=== Step 2: Connect to Neo4j ===")

    from src.graph.connection import load_config, create_driver, verify_connectivity, close_driver
    from src.graph.ppr import PPRConfig, create_gds_client, project_graph, drop_projection, run_ppr

    config = load_config(REPO_ROOT / "config.yaml")
    driver = create_driver(config)

    # Initialize for finally block cleanup
    gds = None
    projection = None

    try:
        if not verify_connectivity(driver):
            logger.error("Cannot reach Neo4j at %s — is it running?", config.uri)
            sys.exit(1)

        logger.info("Connected to Neo4j at %s", config.uri)

        # -----------------------------------------------------------------------
        # Step 3: Clear the database and build the graph
        # -----------------------------------------------------------------------
        logger.info("")
        logger.info("=== Step 3: Clear database and build code graph ===")

        from src.graph.graph_builder import clear_database, build_graph

        cleared = clear_database(driver)
        logger.info("Cleared %d existing nodes", cleared)

        counts = build_graph(driver, all_entities)
        logger.info("Graph creation counts:")
        for key, val in sorted(counts.items()):
            logger.info("  %-16s %d", key, val)

        # -----------------------------------------------------------------------
        # Step 4: Run read-only queries
        # -----------------------------------------------------------------------
        logger.info("")
        logger.info("=== Step 4: Read-only queries ===")

        from src.graph.queries import (
            count_nodes_by_label,
            count_edges_by_type,
            get_neighbors,
            get_file_contents,
            find_callers,
            find_callees,
            get_inheritance_chain,
            find_node_by_name,
        )
        from src.graph.utils import normalize_path

        node_counts = count_nodes_by_label(driver)
        logger.info("Node counts by label:")
        for label, cnt in sorted(node_counts.items()):
            logger.info("  %-12s %d", label, cnt)

        edge_counts = count_edges_by_type(driver)
        logger.info("Edge counts by type:")
        for rel, cnt in sorted(edge_counts.items()):
            logger.info("  %-16s %d", rel, cnt)

        # Derive qualified names directly from the parsed entities — these
        # always match the graph regardless of where the repo is checked out.
        auth_fe = next(fe for fe in all_entities if fe.file_path.endswith("auth_service.py"))
        auth_fp = normalize_path(auth_fe.file_path)
        auth_service_qname = f"{auth_fp}::AuthService"
        register_qname = f"{auth_fp}::AuthService.register"

        validators_fe = next(fe for fe in all_entities if fe.file_path.endswith("validators.py"))
        validators_fp = normalize_path(validators_fe.file_path)
        validate_email_qname = f"{validators_fp}::validate_email"

        models_fe = next(fe for fe in all_entities if fe.file_path.endswith("user.py"))
        models_fp = normalize_path(models_fe.file_path)
        user_qname = f"{models_fp}::User"

        # Neighbors of AuthService
        neighbors = get_neighbors(driver, auth_service_qname)
        logger.info("")
        logger.info("Neighbors of AuthService (%d total):", len(neighbors))
        for n in neighbors:
            logger.info("  [%-8s] %s", n.label, n.name)

        # File contents
        contents = get_file_contents(driver, auth_fp)
        logger.info("")
        logger.info("Contents of auth_service.py (%d entities):", len(contents))
        for n in contents:
            logger.info("  [%-8s] %s", n.label, n.name)

        # Callers of validate_email
        callers = find_callers(driver, validate_email_qname)
        logger.info("")
        logger.info("Callers of validate_email:")
        for c in callers:
            logger.info("  [%-8s] %s", c.label, c.name)

        # Callees of AuthService.register
        callees = find_callees(driver, register_qname)
        logger.info("")
        logger.info("Callees of AuthService.register:")
        for c in callees:
            logger.info("  [%-8s] %s", c.label, c.name)

        # Inheritance chain: User -> BaseModel
        chain = get_inheritance_chain(driver, user_qname)
        logger.info("")
        logger.info("Inheritance chain of User:")
        for c in chain:
            logger.info("  [%-8s] %s", c.label, c.name)

        # -----------------------------------------------------------------------
        # Step 5: GDS projection + Personalized PageRank
        # -----------------------------------------------------------------------
        logger.info("")
        logger.info("=== Step 5: GDS projection + Personalized PageRank ===")

        gds = create_gds_client(driver)
        projection = project_graph(gds)
        logger.info(
            "Projection created: %d nodes, %d relationships",
            projection.node_count(),
            projection.relationship_count(),
        )

        # Seed from AuthService.register — what is most relevant to this method?
        seed = "register"
        cfg = PPRConfig(top_k=10)
        ppr_results = run_ppr(gds, driver, [seed], config=cfg)

        logger.info("")
        logger.info("Top-%d PPR results seeded from '%s':", cfg.top_k, seed)
        logger.info("  %-4s %-12s %-35s %s", "Rank", "Label", "Name", "Score")
        logger.info("  " + "-" * 60)
        for rank, result in enumerate(ppr_results, start=1):
            logger.info(
                "  %-4d %-12s %-35s %.6f",
                rank,
                result.label,
                result.name,
                result.score,
            )

        # -----------------------------------------------------------------------
        # Step 6: Seed node selection (new retrieval layer)
        # -----------------------------------------------------------------------
        logger.info("")
        logger.info("=== Step 6: Seed node selection ===")

        from src.retrieval.seed_selection import extract_seeds

        task = "fix the user registration validation bug"
        logger.info("Task: '%s'", task)

        # Pass the actual file path as stored in the graph (absolute, forward slashes).
        pv = extract_seeds(
            driver,
            task_description=task,
            mentioned_entities=["AuthService"],
            current_file=validators_fp,
        )
        logger.info("Personalization vector (%d seeds):", len(pv.seeds))
        if pv.seeds:
            # Fetch display names for each seed node ID.
            with driver.session() as session:
                result = session.run(
                    "UNWIND $ids AS nid MATCH (n) WHERE id(n)=nid RETURN id(n) AS nid, n.name AS name",
                    ids=list(pv.seeds.keys()),
                )
                id_to_name = {r["nid"]: r["name"] for r in result}
            for nid, weight in sorted(pv.seeds.items(), key=lambda x: -x[1]):
                logger.info("  weight=%.4f  %s", weight, id_to_name.get(nid, f"id={nid}"))

        # -----------------------------------------------------------------------
        # Step 7: IDF reweighting + full PPR from seed vector
        # -----------------------------------------------------------------------
        logger.info("")
        logger.info("=== Step 7: IDF edge reweighting + PPR from seed vector ===")

        from src.retrieval.post_processing import apply_idf_weights

        updated = apply_idf_weights(driver)
        logger.info("IDF weights applied to %d edges", updated)

        # Drop old projection and create a fresh one with IDF weights
        drop_projection(gds)
        projection = project_graph(gds)

        if pv.seeds:
            from src.graph.ppr import run_ppr_from_node_ids

            cfg = PPRConfig(top_k=10)
            ppr_results = run_ppr_from_node_ids(gds, driver, list(pv.seeds.keys()), cfg)

            logger.info("")
            logger.info("Top-%d PPR results from seed vector:", cfg.top_k)
            logger.info("  %-4s %-12s %-45s %s", "Rank", "Label", "Qualified Name", "Score")
            logger.info("  " + "-" * 75)
            for rank, result in enumerate(ppr_results, start=1):
                logger.info(
                    "  %-4d %-12s %-45s %.6f",
                    rank,
                    result.label,
                    result.qualified_name,
                    result.score,
                )

            # -----------------------------------------------------------------------
            # Step 8: format_context (token-budgeted source code)
            # -----------------------------------------------------------------------
            logger.info("")
            logger.info("=== Step 8: format_context (token budget=500) ===")

            from src.retrieval.post_processing import format_context

            # File paths in the graph are absolute; pathlib discards project_root
            # when file_path is itself absolute, so any value works here.
            context_items = format_context(ppr_results, str(REPO_ROOT), token_budget=500)
            logger.info("Context items returned: %d", len(context_items))
            for item in context_items:
                logger.info(
                    "  score=%.4f  tokens=%-4d  %s",
                    item.relevance_score,
                    item.token_count,
                    item.entity_name,
                )

    finally:
        # -----------------------------------------------------------------------
        # Step 9: Clean up
        # -----------------------------------------------------------------------
        logger.info("")
        logger.info("=== Step 9: Clean up ===")

        if gds is not None and projection is not None:
            try:
                drop_projection(gds)
                logger.info("GDS projection dropped")
            except Exception as e:
                logger.warning("Error during projection teardown: %s", e)

        try:
            close_driver(driver)
            logger.info("Neo4j driver closed")
        except Exception as e:
            logger.warning("Error closing Neo4j driver: %s", e)

    logger.info("")
    logger.info("Demo complete. Visit http://localhost:7474 to explore the graph visually.")


if __name__ == "__main__":
    main()
