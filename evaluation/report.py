"""Generate a self-contained HTML report from benchmark results.

Usage:
    python evaluation/report.py <output_dir> [<output_dir2> ...]

Reads per_instance.jsonl + summary.json from each directory and writes
index.html into each directory. Open it in any browser — no server needed.

Multiple directories: also writes a comparison table at the top of each report.
"""

import argparse
import json
from pathlib import Path


# ── data loading ─────────────────────────────────────────────────────────────

def load_results(output_dir: Path) -> tuple[dict, list[dict]]:
    """Return (summary, instances) from an output directory."""
    summary_path = output_dir / "summary.json"
    jsonl_path = output_dir / "per_instance.jsonl"

    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}

    instances: list[dict] = []
    if jsonl_path.exists():
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    instances.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    return summary, instances


# ── HTML helpers ─────────────────────────────────────────────────────────────

def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _recall_cell(value: float) -> str:
    if value == 0.0:
        color = "#fca5a5"  # red-200
    elif value >= 1.0:
        color = "#6ee7b7"  # green-300
    elif value >= 0.5:
        color = "#a7f3d0"  # green-200
    else:
        color = "#fde68a"  # amber-200
    return f'<td style="background:{color};text-align:center">{_pct(value)}</td>'


def _summary_table(summary: dict, label: str) -> str:
    retriever = summary.get("retriever", "ppr")
    ablation = summary.get("ablation", "baseline")
    n = summary.get("n_instances", 0)
    r5 = summary.get("mean_recall_at_5", 0.0)
    r10 = summary.get("mean_recall_at_10", 0.0)
    mmrr = summary.get("mean_mrr", 0.0)
    zero = summary.get("instances_with_zero_recall", 0)
    return f"""
    <table class="summary">
      <caption>{label}</caption>
      <tr><th>Retriever</th><th>Ablation</th><th>N</th>
          <th>Recall@5</th><th>Recall@10</th><th>MRR</th><th>Zero-Recall</th></tr>
      <tr>
        <td>{retriever}</td><td>{ablation}</td><td>{n}</td>
        <td>{_pct(r5)}</td><td>{_pct(r10)}</td><td>{_pct(mmrr)}</td>
        <td>{zero} ({_pct(zero / n if n else 0)})</td>
      </tr>
    </table>"""


def _instance_rows(instances: list[dict]) -> str:
    rows = []
    for inst in instances:
        iid = inst.get("instance_id", "")
        repo = inst.get("repo", "")
        r5 = inst.get("recall_at_5", 0.0)
        r10 = inst.get("recall_at_10", 0.0)
        mmrr = inst.get("mrr", 0.0)
        n_seeds = inst.get("n_seeds", 0)
        elapsed = inst.get("elapsed_seconds", 0.0)
        error = inst.get("error") or ""
        gold = inst.get("gold_files", [])
        predicted = inst.get("predicted_files", [])

        # Annotate predicted list: bold if it's a gold file
        gold_set = set(gold)
        pred_html = []
        for i, fp in enumerate(predicted[:20]):  # cap display at 20
            style = "font-weight:bold;color:#059669" if fp in gold_set else ""
            pred_html.append(f'<span style="{style}">{i+1}. {fp}</span>')
        if len(predicted) > 20:
            pred_html.append(f"<em>…+{len(predicted)-20} more</em>")

        error_td = f'<td style="color:#dc2626;font-size:0.75em">{error[:120]}</td>' if error else "<td></td>"
        rows.append(f"""
        <tr>
          <td class="mono">{iid}</td>
          <td>{repo}</td>
          {_recall_cell(r5)}
          {_recall_cell(r10)}
          {_recall_cell(mmrr)}
          <td style="text-align:center">{n_seeds}</td>
          <td style="text-align:center">{elapsed:.1f}s</td>
          <td class="mono small">{'<br>'.join(gold)}</td>
          <td class="mono small">{'<br>'.join(pred_html)}</td>
          {error_td}
        </tr>""")
    return "\n".join(rows)


def _recall_histogram_data(instances: list[dict]) -> str:
    """Bucket R@10 into 0%, 1-49%, 50-99%, 100%."""
    buckets = {"0%": 0, "1–49%": 0, "50–99%": 0, "100%": 0}
    for inst in instances:
        v = inst.get("recall_at_10", 0.0)
        if v == 0.0:
            buckets["0%"] += 1
        elif v < 0.5:
            buckets["1–49%"] += 1
        elif v < 1.0:
            buckets["50–99%"] += 1
        else:
            buckets["100%"] += 1
    labels = list(buckets.keys())
    values = list(buckets.values())
    return f"labels: {labels}, data: {values}"


def generate_html(output_dir: Path, all_dirs: list[Path]) -> str:
    """Build the full HTML string for output_dir."""
    summary, instances = load_results(output_dir)
    retriever = summary.get("retriever", output_dir.name)

    # Comparison table (only if multiple dirs provided)
    comparison_html = ""
    if len(all_dirs) > 1:
        rows = []
        for d in all_dirs:
            s, _ = load_results(d)
            lbl = s.get("retriever", d.name)
            n = s.get("n_instances", 0)
            rows.append(
                f"<tr><td>{lbl}</td><td>{d.name}</td>"
                f"<td>{_pct(s.get('mean_recall_at_5',0))}</td>"
                f"<td>{_pct(s.get('mean_recall_at_10',0))}</td>"
                f"<td>{_pct(s.get('mean_mrr',0))}</td>"
                f"<td>{s.get('instances_with_zero_recall',0)}</td>"
                f"<td>{n}</td></tr>"
            )
        comparison_html = f"""
    <h2>Cross-run Comparison</h2>
    <table class="summary">
      <tr><th>Retriever</th><th>Directory</th><th>Recall@5</th>
          <th>Recall@10</th><th>MRR</th><th>Zero-Recall</th><th>N</th></tr>
      {''.join(rows)}
    </table>"""

    # Histogram data
    hist = _recall_histogram_data(instances)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>CodeGraph Benchmark — {retriever} — {output_dir.name}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 1400px; margin: 0 auto; padding: 1rem; color: #1e293b; }}
    h1 {{ font-size: 1.5rem; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 1.1rem; margin-top: 2rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.25rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 0.75rem 0; font-size: 0.85rem; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 4px 8px; vertical-align: top; }}
    th {{ background: #f1f5f9; text-align: left; }}
    table.summary td, table.summary th {{ padding: 6px 12px; }}
    caption {{ text-align: left; font-weight: 600; margin-bottom: 4px; }}
    .mono {{ font-family: monospace; font-size: 0.78rem; }}
    .small {{ font-size: 0.75rem; }}
    input[type=text] {{ width: 100%; padding: 4px 8px; border: 1px solid #94a3b8; border-radius: 4px; margin-bottom: 0.5rem; }}
    #chart-wrap {{ max-width: 480px; margin: 1rem 0; }}
    tr:nth-child(even) {{ background: #f8fafc; }}
  </style>
</head>
<body>
  <h1>CodeGraph Benchmark Report</h1>
  <p>Directory: <code>{output_dir}</code></p>

  {comparison_html}

  <h2>Summary — {retriever}</h2>
  {_summary_table(summary, retriever)}

  <div id="chart-wrap">
    <canvas id="hist"></canvas>
  </div>

  <h2>Per-Instance Results ({len(instances)} instances)</h2>
  <input type="text" id="filter" placeholder="Filter by instance_id or repo…" oninput="filterTable()">
  <table id="inst-table">
    <thead>
      <tr>
        <th>Instance ID</th><th>Repo</th>
        <th>R@5</th><th>R@10</th><th>MRR</th>
        <th>Seeds</th><th>Time</th>
        <th>Gold Files</th><th>Predicted (top 20, <b>bold</b>=hit)</th>
        <th>Error</th>
      </tr>
    </thead>
    <tbody>
      {_instance_rows(instances)}
    </tbody>
  </table>

  <script>
    // Histogram
    new Chart(document.getElementById('hist'), {{
      type: 'bar',
      data: {{
        {hist},
        datasets: [{{ label: 'Instances by Recall@10',
          data: data, backgroundColor: ['#fca5a5','#fde68a','#a7f3d0','#6ee7b7'] }}]
      }},
      options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true }} }} }}
    }});

    // Filter
    function filterTable() {{
      const q = document.getElementById('filter').value.toLowerCase();
      document.querySelectorAll('#inst-table tbody tr').forEach(row => {{
        row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
      }});
    }}
  </script>
</body>
</html>"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate HTML report from benchmark results")
    parser.add_argument("dirs", nargs="+", help="Output directories containing per_instance.jsonl")
    args = parser.parse_args()

    all_dirs = [Path(d) for d in args.dirs]
    for d in all_dirs:
        html = generate_html(d, all_dirs)
        out = d / "index.html"
        out.write_text(html, encoding="utf-8")
        print(f"Written: {out}")


if __name__ == "__main__":
    main()
