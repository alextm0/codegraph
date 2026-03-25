# CodeGraph Nightly Ablation Pipeline
# This script runs all remaining Iteration 2 experiments sequentially.
# It skips benchmarking for any result folders that already exist (with a summary.json).

$results_root = "evaluation/results"
$driver_check = python -c "from codegraph.core.graph.connection import create_driver, load_config; create_driver(load_config('config.yaml'))"

if ($LASTEXITCODE -ne 0) {
    Write-Error "Neo4j is not reachable. Please start Neo4j before running this script."
    exit 1
}

$experiments = @(
    # Format: @{ name = "folder_suffix"; ablation = "config_name"; retriever = "ppr" }
    @{ name = "no_expansion"; ablation = "no_structural_expansion"; retriever = "ppr" },
    @{ name = "bm25"; ablation = "baseline"; retriever = "bm25" },
    @{ name = "alpha_070"; ablation = "uniform_alpha_070"; retriever = "ppr" },
    @{ name = "top_30"; ablation = "uniform_top_k_30"; retriever = "ppr" }
)

Write-Host "--- Starting Nightly Pipeline Iteration 2 ---" -ForegroundColor Cyan

foreach ($exp in $experiments) {
    $out_path = "$results_root/iteration_2_$($exp.name)"
    $sum_path = "$out_path/summary.json"
    $log_path = "$out_path.log"

    if (Test-Path $sum_path) {
        Write-Host "Skipping $($exp.name) - already completed." -ForegroundColor Gray
        continue
    }

    Write-Host "Running $($exp.name) (Ablation: $($exp.ablation), Retriever: $($exp.retriever))" -ForegroundColor Yellow
    Write-Host "Output: $out_path"
    
    # Run the benchmark
    python -m evaluation.swe_bench_runner --retriever $($exp.retriever) --ablation $($exp.ablation) --output $out_path --limit 0 2>&1 | tee $log_path

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: $($exp.name) failed! Moving to next experiment..." -ForegroundColor Red
    } else {
        Write-Host "SUCCESS: $($exp.name) complete.`n" -ForegroundColor Green
    }
}

Write-Host "--- Pipeline Finished ---" -ForegroundColor Cyan
