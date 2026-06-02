# Thesis Defense Demo Script

## Preparation (Pre-Demo)
1. Ensure Neo4j Desktop 2 is running with the correct active database.
2. Clear the Neo4j database: `codegraph doctor --reset` (or similar cleanup).
3. Have Claude Desktop running with the MCP server configured.

## Act 1: The Visualizer (Human Exploration)
1. Open terminal: `codegraph visualize`
2. Open browser. Show the empty onboarding screen.
3. Paste: `https://github.com/pallets/flask` (or your chosen demo repo).
4. Click "Index Repository". Explain that it is parsing the AST and building the Neo4j graph in real-time.
5. The full codebase graph appears. Show zooming, panning, and hovering.
6. Run Query: "How does routing work?"
7. Show how the graph dims, highlighting the shortest paths and ranking the files on the right sidebar. Click a node to show the Inspector.

## Act 2: The MCP Server (AI Collaboration)
1. Open Claude Desktop.
2. Prompt: "I am working on the flask routing. Can you use your tools to find the relevant context and explain how I would add a new route?"
3. Show Claude calling `get_relevant_context`.
4. Explain how Claude gets the exact same structural ranking scores seen in the UI, proving the system's consistency.

## Act 3: The CLI (Developer Speed)
1. Open terminal in a new directory.
2. Run `codegraph init` and walk through the interactive wizard.
