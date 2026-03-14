"""Retrieval baselines for comparison against CodeGraph PPR."""

import logging
import random
import re
from neo4j import Driver
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


def _fetch_all_files(driver: Driver) -> list[str]:
    """Return all File node paths from the graph."""
    with driver.session() as session:
        result = session.run("MATCH (f:File) RETURN f.file_path AS path")
        return [r["path"] for r in result if r["path"]]


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    return [tok for tok in re.split(r"[^a-z0-9_]+", text.lower()) if tok]


class RandomBaseline:
    """Floor baseline: return k random files from the graph.

    Each call draws a new random sample, so aggregate accuracy across many
    instances gives the expected random-chance recall.
    """

    def run(self, driver: Driver, task_description: str, k: int = 10) -> list[str]:
        """Return k randomly sampled file paths."""
        files = _fetch_all_files(driver)
        if not files:
            return []
        k_actual = min(k, len(files))
        random.seed(hash(task_description))
        return random.sample(files, k_actual)


class BM25Baseline:
    """Text-retrieval baseline: BM25 over file-level content (signatures + docstrings).

    Scores every Function and Method in the graph, then maps the top-k nodes
    back to their containing files (deduplicated, preserving rank order).
    """

    def run(self, driver: Driver, task_description: str, k: int = 10) -> list[str]:
        """Return up to k file paths ranked by BM25 relevance."""
        rows = self._fetch_nodes(driver)
        if not rows:
            return []

        corpus = [_tokenize(r["signature"] + " " + r["docstring"]) for r in rows]
        query = _tokenize(task_description)
        if not query:
            return []

        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query)
        ranked = sorted(zip(scores, rows), key=lambda x: x[0], reverse=True)

        seen: set[str] = set()
        files: list[str] = []
        for _score, row in ranked:
            fp = row["file_path"]
            if fp and fp not in seen:
                seen.add(fp)
                files.append(fp)
            if len(files) >= k:
                break
        return files

    def _fetch_nodes(self, driver: Driver) -> list[dict]:
        """Fetch all Function/Method nodes with text fields."""
        rows: list[dict] = []
        with driver.session() as session:
            result = session.run(
                """
                MATCH (n) WHERE n:Function OR n:Method
                RETURN n.file_path AS file_path,
                       coalesce(n.signature, "") AS signature,
                       coalesce(n.docstring, "") AS docstring
                """
            )
            for r in result:
                rows.append({
                    "file_path": r["file_path"] or "",
                    "signature": r["signature"] or "",
                    "docstring": r["docstring"] or "",
                })
        return rows


class OneHopBaseline:
    """Graph baseline: find seed nodes via BM25, return files of direct neighbors.

    Tests whether simple graph expansion (1-hop ego network) adds value beyond
    pure text retrieval. If PPR substantially beats this, multi-hop traversal
    is earning its keep.
    """

    def run(self, driver: Driver, task_description: str, k: int = 10) -> list[str]:
        """Return files reachable within one hop of BM25-selected seed nodes."""
        bm25 = BM25Baseline()
        seed_files = bm25.run(driver, task_description, k=5)
        if not seed_files:
            return []

        neighbor_files = self._one_hop_files(driver, seed_files)

        # Merge seed files + neighbor files, deduplicated, seed files first.
        seen: set[str] = set()
        result: list[str] = []
        for fp in seed_files + neighbor_files:
            if fp and fp not in seen:
                seen.add(fp)
                result.append(fp)
            if len(result) >= k:
                break
        return result

    def _one_hop_files(self, driver: Driver, seed_files: list[str]) -> list[str]:
        """Return file_path values of nodes directly connected to any seed file node."""
        with driver.session() as session:
            result = session.run(
                """
                MATCH (seed:File)-[r]-(neighbor)
                WHERE seed.file_path IN $paths AND neighbor.file_path IS NOT NULL
                WITH neighbor.file_path AS file_path, count(r) AS edge_count
                ORDER BY edge_count DESC, file_path ASC
                RETURN file_path
                """,
                paths=seed_files,
            )
            return [r["file_path"] for r in result if r["file_path"]]
