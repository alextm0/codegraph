"""Retrieval metrics for CodeGraph benchmark evaluation."""

import statistics


def recall_at_k(gold_files: list[str], predicted_files: list[str], k: int) -> float:
    """Fraction of gold files found in the top-k predictions.

    Args:
        gold_files: Ground-truth files that need to be retrieved.
        predicted_files: Ranked list of files returned by the retrieval system.
        k: Cut-off rank.

    Returns:
        Value in [0.0, 1.0]. Returns 0.0 if gold_files is empty.
    """
    if not gold_files:
        return 0.0
    gold = set(gold_files)
    top_k = set(predicted_files[:k])
    return len(gold & top_k) / len(gold)


def mrr(gold_files: list[str], predicted_files: list[str]) -> float:
    """Mean Reciprocal Rank: reciprocal of the rank of the first correct prediction.

    Returns 0.0 if no gold file appears in predicted_files.
    """
    gold = set(gold_files)
    for rank, pred in enumerate(predicted_files, start=1):
        if pred in gold:
            return 1.0 / rank
    return 0.0


def aggregate_metrics(instance_results: list[dict]) -> dict:
    """Compute mean/median recall@k and MRR across all instances.

    Args:
        instance_results: List of per-instance result dicts, each containing
            at minimum: recall_at_5, recall_at_10, mrr, error.

    Returns:
        Summary dict with mean and median for each metric, plus zero-recall count.
        Includes a 'success_only' section for metrics excluding errored instances.
    """
    if not instance_results:
        return {
            "n_instances": 0,
            "mean_recall_at_5": 0.0,
            "median_recall_at_5": 0.0,
            "mean_recall_at_10": 0.0,
            "median_recall_at_10": 0.0,
            "mean_mrr": 0.0,
            "median_mrr": 0.0,
            "instances_with_zero_recall": 0,
            "success_only": None,
        }

    def _calc(results: list[dict]) -> dict:
        r5 = [r["recall_at_5"] for r in results]
        r10 = [r["recall_at_10"] for r in results]
        mrr_vals = [r["mrr"] for r in results]
        zero_recall = sum(1 for v in r10 if v == 0.0)

        return {
            "n_instances": len(results),
            "mean_recall_at_5": statistics.mean(r5) if r5 else 0.0,
            "median_recall_at_5": statistics.median(r5) if r5 else 0.0,
            "mean_recall_at_10": statistics.mean(r10) if r10 else 0.0,
            "median_recall_at_10": statistics.median(r10) if r10 else 0.0,
            "mean_mrr": statistics.mean(mrr_vals) if mrr_vals else 0.0,
            "median_mrr": statistics.median(mrr_vals) if mrr_vals else 0.0,
            "instances_with_zero_recall": zero_recall,
        }

    summary = _calc(instance_results)

    success_results = [r for r in instance_results if not r.get("error")]
    if len(success_results) < len(instance_results):
        summary["success_only"] = _calc(success_results)
    else:
        summary["success_only"] = None

    return summary
