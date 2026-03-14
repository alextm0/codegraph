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
            at minimum: recall_at_5, recall_at_10, mrr.

    Returns:
        Summary dict with mean and median for each metric, plus zero-recall count.
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
        }

    r5 = [r["recall_at_5"] for r in instance_results]
    r10 = [r["recall_at_10"] for r in instance_results]
    mrr_vals = [r["mrr"] for r in instance_results]
    zero_recall = sum(1 for v in r10 if v == 0.0)

    return {
        "n_instances": len(instance_results),
        "mean_recall_at_5": statistics.mean(r5),
        "median_recall_at_5": statistics.median(r5),
        "mean_recall_at_10": statistics.mean(r10),
        "median_recall_at_10": statistics.median(r10),
        "mean_mrr": statistics.mean(mrr_vals),
        "median_mrr": statistics.median(mrr_vals),
        "instances_with_zero_recall": zero_recall,
    }
