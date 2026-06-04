"""Run multiple SWE-bench ablations sequentially in one command.

Each ablation invokes ``evaluation.swe_bench_runner`` as a subprocess so failures
are isolated and progress is visible per run. After all runs, writes a comparison
table and picks the best configuration by Recall@10 (then fewer zero-recall).

Usage:
    python -m evaluation.verify_benchmark_setup --live

    # Quick uniform vs weighted (10 instances):
    python -m evaluation.run_ablation_sweep --preset quick --limit 10
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from evaluation.ablations import PRESETS, preset_names, resolve_preset
from evaluation.compare_runs import load_summary, print_markdown


@dataclass(frozen=True)
class SweepJob:
    """One benchmark run in the sweep."""

    label: str
    ablation: str
    file_rank_by: str = "first_entity"

    @property
    def output_name(self) -> str:
        if self.file_rank_by == "first_entity":
            return self.label
        if self.label.endswith(f"_{self.file_rank_by}"):
            return self.label
        return f"{self.label}__rank_{self.file_rank_by}"


def build_jobs(
    ablation_names: list[str],
    *,
    include_file_rank_variants: bool,
) -> list[SweepJob]:
    """Expand ablation list into sweep jobs."""
    jobs: list[SweepJob] = []
    for name in ablation_names:
        jobs.append(SweepJob(label=name, ablation=name))
        if include_file_rank_variants and name == "baseline":
            jobs.append(
                SweepJob(
                    label="baseline_max_score",
                    ablation="baseline",
                    file_rank_by="max_score",
                )
            )
    return jobs


def _is_complete(output_dir: Path, expected_n: int) -> bool:
    """True if summary.json exists with expected instance count."""
    summary_path = output_dir / "summary.json"
    if not summary_path.exists():
        return False
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return summary.get("n_instances", 0) >= expected_n and summary.get("n_instances", 0) > 0


def _should_resume(output_dir: Path, expected_n: int) -> bool:
    """Resume when a prior run left partial per_instance.jsonl."""
    if expected_n <= 0 or _is_complete(output_dir, expected_n):
        return False
    return (output_dir / "per_instance.jsonl").exists()


def _run_single(
    job: SweepJob,
    *,
    python: str,
    cache_dir: str,
    output_dir: Path,
    limit: int,
    config_path: str,
    verbose: bool,
    skip_preflight: bool,
    instance_ids_file: str | None = None,
    repo_prefix: str | None = None,
    subset_name: str | None = None,
    compare_baseline: str | None = None,
) -> int:
    """Run one ablation via subprocess; return exit code."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        python,
        "-m",
        "evaluation.swe_bench_runner",
        "--cache-dir",
        cache_dir,
        "--output",
        str(output_dir),
        "--ablation",
        job.ablation,
        "--grouping",
        "repo_commit",
        "--file-rank-by",
        job.file_rank_by,
    ]
    if limit > 0:
        cmd.extend(["--limit", str(limit)])
    if _should_resume(output_dir, limit):
        cmd.append("--resume")
    if verbose:
        cmd.append("--verbose")
    if skip_preflight:
        cmd.append("--skip-preflight")
    if instance_ids_file:
        cmd.extend(["--instance-ids-file", instance_ids_file])
    if repo_prefix:
        cmd.extend(["--repo-prefix", repo_prefix])
    if subset_name:
        cmd.extend(["--subset-name", subset_name])
    if compare_baseline:
        cmd.extend(["--compare-baseline", compare_baseline])

    log_path = output_dir / "run.log"
    print(f"\n{'=' * 72}", file=sys.stderr, flush=True)
    print(
        f"SWEEP: {job.output_name} (ablation={job.ablation}, "
        f"file_rank_by={job.file_rank_by})",
        file=sys.stderr,
        flush=True,
    )
    print(f"  output: {output_dir}", file=sys.stderr, flush=True)
    print(f"  command: {' '.join(cmd)}", file=sys.stderr, flush=True)
    print(
        f"  log: {log_path}  (live: tail -f {log_path})",
        file=sys.stderr,
        flush=True,
    )
    print(f"{'=' * 72}\n", file=sys.stderr, flush=True)

    with open(log_path, "a", encoding="utf-8") as log_fh:
        log_fh.write(f"\n--- started {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        log_fh.write(" ".join(cmd) + "\n\n")
        log_fh.flush()

    # Inherit stdout/stderr so [bench] progress lines appear in the terminal.
    proc = subprocess.run(cmd)
    return proc.returncode


def _pick_best(rows: list[tuple[str, dict]]) -> tuple[str, dict]:
    """Select best run: highest R@10, then lowest zero-recall, then MRR."""

    def sort_key(item: tuple[str, dict]) -> tuple[float, int, float]:
        _label, s = item
        r10 = float(s.get("mean_recall_at_10", 0.0))
        zero = int(s.get("instances_with_zero_recall", 999999))
        mrr = float(s.get("mean_mrr", 0.0))
        return (r10, -zero, mrr)

    return max(rows, key=sort_key)


def _write_sweep_summary(
    output_root: Path,
    rows: list[tuple[str, dict]],
    jobs: list[SweepJob],
    *,
    limit: int,
    preset: str | None,
) -> dict:
    """Write sweep_summary.json and return its contents."""
    best_label, best_summary = _pick_best(rows)
    payload = {
        "preset": preset,
        "limit": limit,
        "jobs": [
            {
                "label": j.output_name,
                "ablation": j.ablation,
                "file_rank_by": j.file_rank_by,
                "output_dir": str(output_root / j.output_name),
            }
            for j in jobs
        ],
        "results": [
            {
                "label": label,
                "mean_recall_at_10": s.get("mean_recall_at_10"),
                "mean_recall_at_5": s.get("mean_recall_at_5"),
                "mean_mrr": s.get("mean_mrr"),
                "instances_with_zero_recall": s.get("instances_with_zero_recall"),
                "n_instances": s.get("n_instances"),
                "ablation": s.get("ablation"),
                "git_commit": s.get("git_commit"),
            }
            for label, s in rows
        ],
        "best": {
            "label": best_label,
            "mean_recall_at_10": best_summary.get("mean_recall_at_10"),
            "instances_with_zero_recall": best_summary.get(
                "instances_with_zero_recall"
            ),
            "ablation": best_summary.get("ablation"),
        },
    }
    path = output_root / "sweep_summary.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def run_sweep(
    jobs: list[SweepJob],
    *,
    output_root: Path,
    limit: int,
    expected_instances: int,
    cache_dir: str,
    config_path: str,
    python: str | None = None,
    verbose: bool = False,
    skip_preflight: bool = False,
    skip_completed: bool = False,
    dry_run: bool = False,
    preset: str | None = None,
    instance_ids_file: str | None = None,
    repo_prefix: str | None = None,
    subset_name: str | None = None,
    compare_baseline: str | None = None,
) -> int:
    """Execute all jobs sequentially; return exit code."""
    py = python or sys.executable
    output_root.mkdir(parents=True, exist_ok=True)
    sweep_log = output_root / "sweep.log"

    if dry_run:
        print(f"Would run {len(jobs)} jobs under {output_root} (limit={limit}):")
        for job in jobs:
            print(f"  - {job.output_name}: ablation={job.ablation} rank={job.file_rank_by}")
        return 0

    with open(sweep_log, "a", encoding="utf-8") as sweep_fh:
        sweep_fh.write(
            f"\n=== sweep started {time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"preset={preset!r} limit={limit} jobs={len(jobs)} ===\n"
        )

    failures: list[str] = []
    for i, job in enumerate(jobs, start=1):
        out_dir = output_root / job.output_name
        if skip_completed and expected_instances > 0 and _is_complete(
            out_dir, expected_instances
        ):
            print(
                f"[sweep {i}/{len(jobs)}] SKIP {job.output_name} (already complete)",
                file=sys.stderr,
                flush=True,
            )
            continue

        preflight = skip_preflight or i > 1
        code = _run_single(
            job,
            python=py,
            cache_dir=cache_dir,
            output_dir=out_dir,
            limit=limit,
            config_path=config_path,
            verbose=verbose,
            skip_preflight=preflight,
            instance_ids_file=instance_ids_file,
            repo_prefix=repo_prefix,
            subset_name=subset_name,
            compare_baseline=compare_baseline,
        )
        if code != 0:
            failures.append(f"{job.output_name} exited with code {code}")

    rows: list[tuple[str, dict]] = []
    for job in jobs:
        out_dir = output_root / job.output_name
        summary_path = out_dir / "summary.json"
        if not summary_path.exists():
            failures.append(f"{job.output_name}: missing summary.json")
            continue
        summary = load_summary(str(out_dir))
        rows.append((job.output_name, summary))

    if rows:
        print("\n--- Sweep comparison ---", file=sys.stderr, flush=True)
        print_markdown(rows)
        sweep = _write_sweep_summary(
            output_root, rows, jobs, limit=limit, preset=preset
        )
        best = sweep["best"]
        print(
            f"\nBest: {best['label']} — R@10={best['mean_recall_at_10']:.4f}, "
            f"zero_recall={best['instances_with_zero_recall']}",
            file=sys.stderr,
            flush=True,
        )
        print(f"Wrote {output_root / 'sweep_summary.json'}", file=sys.stderr, flush=True)

    if failures:
        print("\nSweep finished with errors:", file=sys.stderr, flush=True)
        for msg in failures:
            print(f"  - {msg}", file=sys.stderr, flush=True)
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SWE-bench ablations sequentially and compare results"
    )
    parser.add_argument(
        "--preset",
        choices=preset_names(),
        default="quick",
        help="Named ablation list (default: quick)",
    )
    parser.add_argument(
        "--ablation",
        action="append",
        dest="ablations",
        help="Additional ablation name(s); can combine with --preset",
    )
    parser.add_argument(
        "--output-root",
        default="evaluation/results/ablation_sweep",
        help="Parent directory; each ablation writes to <root>/<name>/",
    )
    parser.add_argument("--limit", type=int, default=50, help="Instances per ablation")
    parser.add_argument("--cache-dir", default=".codegraph_cache/repos")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Pass --skip-preflight to every swe_bench_runner subprocess",
    )
    parser.add_argument(
        "--skip-completed",
        action="store_true",
        help="Skip ablations whose summary.json already has n_instances >= limit",
    )
    parser.add_argument(
        "--file-rank-variant",
        action="store_true",
        help="Also run baseline with --file-rank-by max_score",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned runs without executing",
    )
    parser.add_argument(
        "--instance-ids-file",
        default=None,
        help="Subset: JSON list of instance_ids or file.json:tier_key",
    )
    parser.add_argument(
        "--repo-prefix",
        default=None,
        help="Only run instances for repos matching this prefix",
    )
    parser.add_argument(
        "--subset-name",
        default=None,
        help="Stored in summary.json for filtered runs",
    )
    parser.add_argument(
        "--compare-baseline",
        default=None,
        help="Reference summary.json path written into each run summary",
    )
    parser.add_argument(
        "--python",
        default=None,
        help="Python executable (default: current interpreter)",
    )
    args = parser.parse_args()
    Path(args.output_root).mkdir(parents=True, exist_ok=True)

    from evaluation.dataset import DatasetManager
    from evaluation.instance_filter import resolve_instance_ids_arg

    instance_ids: set[str] | None = None
    subset_name = args.subset_name
    if args.instance_ids_file:
        instance_ids, tier_label = resolve_instance_ids_arg(args.instance_ids_file)
        subset_name = subset_name or tier_label
    expected = len(
        DatasetManager().load_filtered(
            limit=args.limit,
            instance_ids=instance_ids,
            repo_prefix=args.repo_prefix,
        )
    )
    if expected == 0:
        raise SystemExit("No instances matched filters.")

    names: list[str] = []
    if args.preset:
        names.extend(resolve_preset(args.preset))
    if args.ablations:
        for ab in args.ablations:
            if ab not in names:
                names.append(ab)
    if not names:
        raise SystemExit("No ablations selected. Use --preset or --ablation.")

    jobs = build_jobs(
        names,
        include_file_rank_variants=args.file_rank_variant,
    )
    code = run_sweep(
        jobs,
        output_root=Path(args.output_root),
        limit=args.limit,
        expected_instances=expected,
        cache_dir=args.cache_dir,
        config_path=args.config,
        python=args.python,
        verbose=args.verbose,
        skip_preflight=args.skip_preflight,
        skip_completed=args.skip_completed,
        dry_run=args.dry_run,
        preset=args.preset,
        instance_ids_file=args.instance_ids_file,
        repo_prefix=args.repo_prefix,
        subset_name=subset_name,
        compare_baseline=args.compare_baseline,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
