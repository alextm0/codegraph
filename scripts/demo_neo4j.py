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
    logger.info("\n=== Step 2: Connect to Neo4j ===")

    from src.graph.connection import Neo4jConfig, create_driver, verify_connectivity

    config = Neo4jConfig()  # bolt://localhost:7687, neo4j/password
    driver = create_driver(config)

    if not verify_connectivity(driver):
        logger.error("Cannot reach Neo4j at %s — is it running?", config.uri)
        sys.exit(1)

    logger.info("Connected to Neo4j at %s", config.uri)

    # -----------------------------------------------------------------------
    # Step 3: Clear the database and build the graph
    # -----------------------------------------------------------------------
    logger.info("\n=== Step 3: Clear database and build code graph ===")

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
    logger.info("\n=== Step 4: Read-only queries ===")

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

    node_counts = count_nodes_by_label(driver)
    logger.info("Node counts by label:")
    for label, cnt in sorted(node_counts.items()):
        logger.info("  %-12s %d", label, cnt)

    edge_counts = count_edges_by_type(driver)
    logger.info("Edge counts by type:")
    for rel, cnt in sorted(edge_counts.items()):
        logger.info("  %-16s %d", rel, cnt)

    # Neighbors of AuthService
    auth_service_qname = "services/auth_service.py::AuthService"
    neighbors = get_neighbors(driver, auth_service_qname)
    logger.info("\nNeighbors of %s (%d total):", auth_service_qname, len(neighbors))
    for n in neighbors:
        logger.info("  [%s] %s", n.label, n.qualified_name)

    # File contents
    file_path = "services/auth_service.py"
    contents = get_file_contents(driver, file_path)
    logger.info("\nContents of %s (%d entities):", file_path, len(contents))
    for n in contents:
        logger.info("  [%s] %s", n.label, n.name)

    # Callers of validate_email
    validate_email_qname = "utils/validators.py::validate_email"
    callers = find_callers(driver, validate_email_qname)
    logger.info("\nCallers of %s:", validate_email_qname)
    for c in callers:
        logger.info("  [%s] %s", c.label, c.qualified_name)

    # Callees of AuthService.register
    register_qname = "services/auth_service.py::AuthService.register"
    callees = find_callees(driver, register_qname)
    logger.info("\nCallees of %s:", register_qname)
    for c in callees:
        logger.info("  [%s] %s", c.label, c.qualified_name)

    # Inheritance chain: User -> BaseModel
    user_qname = "models/user.py::User"
    chain = get_inheritance_chain(driver, user_qname)
    logger.info("\nInheritance chain of %s:", user_qname)
    for c in chain:
        logger.info("  [%s] %s", c.label, c.qualified_name)

    # -----------------------------------------------------------------------
    # Step 5: GDS projection + Personalized PageRank
    # -----------------------------------------------------------------------
    logger.info("\n=== Step 5: GDS projection + Personalized PageRank ===")

    from src.graph.ppr import PPRConfig, create_gds_client, project_graph, drop_projection, run_ppr

    gds = create_gds_client(driver)
    graph = project_graph(gds)
    logger.info(
        "Projection created: %d nodes, %d relationships",
        graph.node_count(),
        graph.relationship_count(),
    )

    # Seed from AuthService.register — what is most relevant to this method?
    seed = "register"
    cfg = PPRConfig(top_k=10)
    ppr_results = run_ppr(gds, driver, [seed], config=cfg)

    logger.info("\nTop-%d PPR results seeded from '%s':", cfg.top_k, seed)
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
    # Step 6: Clean up
    # -----------------------------------------------------------------------
    logger.info("\n=== Step 6: Clean up ===")

    drop_projection(gds)
    logger.info("GDS projection dropped")

    from src.graph.connection import close_driver
    close_driver(driver)
    logger.info("Neo4j driver closed")

    logger.info("\nDemo complete. Visit http://localhost:7474 to explore the graph visually.")


if __name__ == "__main__":
    main()
