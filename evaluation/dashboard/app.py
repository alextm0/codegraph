"""SWE-bench evaluation dashboard — Textual TUI."""
from __future__ import annotations

import asyncio
import webbrowser
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    ProgressBar,
    Select,
    Static,
)

from evaluation.dashboard import models
from evaluation.dashboard.models import LiveProgress, RunConfig, RunRecord
from evaluation.dashboard import parser, runner, state

# ─────────────────────────── helpers ────────────────────────────────────────

_RESULTS_ROOT = Path(__file__).parent.parent / "results"
_STATUS_STYLE = {
    "running": "bold green",
    "completed": "bold blue",
    "failed": "bold red",
    "stopped": "bold yellow",
    "queued": "dim",
}


def _styled_status(status: str) -> str:
    style = _STATUS_STYLE.get(status, "")
    return f"[{style}]{status}[/{style}]" if style else status


def _fmt_metric(v: float) -> str:
    return f"{v:.3f}"


def _fmt_eta(eta: float | None) -> str:
    if eta is None:
        return "—"
    h, rem = divmod(int(eta), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m{s:02d}s"


def _fmt_throughput(t: float) -> str:
    return f"{t:.1f}/hr" if t > 0 else "—"


# ─────────────────────────── Runs list screen ────────────────────────────────

class RunsScreen(Screen):
    BINDINGS = [
        Binding("n", "new_run", "New Run"),
        Binding("s", "stop_run", "Stop"),
        Binding("r", "resume_run", "Resume"),
        Binding("c", "toggle_compare", "Compare"),
        Binding("enter", "view_detail", "Detail"),
        Binding("q", "app.quit", "Quit"),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._compare_ids: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DataTable(id="runs_table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#runs_table", DataTable)
        table.add_columns("ID", "Status", "Retriever", "Ablation", "Done", "R@10", "MRR", "Started")
        self._refresh_table()
        self.set_interval(3, self._refresh_table)

    def _refresh_table(self) -> None:
        table = self.query_one("#runs_table", DataTable)
        runs = state.list_runs()
        cursor_key = table.cursor_row

        table.clear()
        for run in runs:
            # Compute live progress from JSONL
            jsonl = Path(run.output_dir) / "per_instance.jsonl"
            instances, _ = parser.read_instances(jsonl)
            started = datetime.fromisoformat(run.started_at) if run.started_at else datetime.now()
            prog = parser.compute_live_progress(instances, started, None)

            marker = "✓ " if run.id in self._compare_ids else "  "
            cfg = run.config
            retriever = cfg.retriever if cfg else "—"
            ablation = cfg.ablation if cfg else "—"
            started_str = run.started_at[:16] if run.started_at else "—"

            table.add_row(
                f"{marker}{run.id}",
                _styled_status(run.status),
                retriever,
                ablation,
                str(prog.n_done),
                _fmt_metric(prog.mean_recall_at_10),
                _fmt_metric(prog.mean_mrr),
                started_str,
                key=run.id,
            )

        # Restore cursor position
        if cursor_key is not None and cursor_key < table.row_count:
            table.move_cursor(row=cursor_key)

    def _selected_run_id(self) -> str | None:
        table = self.query_one("#runs_table", DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(row_key.value) if row_key.value else None

    def action_view_detail(self) -> None:
        run_id = self._selected_run_id()
        if run_id:
            # Strip compare marker prefix
            clean_id = run_id.strip().lstrip("✓ ").strip()
            run = state.get_run(clean_id)
            if run:
                self.app.push_screen(RunDetailScreen(run, self.app._procs))

    def action_stop_run(self) -> None:
        run_id = self._selected_run_id()
        if not run_id:
            return
        clean_id = run_id.strip().lstrip("✓ ").strip()
        proc = self.app._procs.get(clean_id)
        if proc:
            asyncio.create_task(runner.stop_run(proc))

    def action_resume_run(self) -> None:
        run_id = self._selected_run_id()
        if not run_id:
            return
        clean_id = run_id.strip().lstrip("✓ ").strip()
        run = state.get_run(clean_id)
        if run and run.config:
            self.app.push_screen(ResumeScreen(run))

    def action_new_run(self) -> None:
        self.app.push_screen(NewRunScreen())

    def action_toggle_compare(self) -> None:
        run_id = self._selected_run_id()
        if not run_id:
            return
        clean_id = run_id.strip().lstrip("✓ ").strip()
        if clean_id in self._compare_ids:
            self._compare_ids.discard(clean_id)
        else:
            self._compare_ids.add(clean_id)
        if len(self._compare_ids) >= 2:
            self.app.push_screen(CompareScreen(list(self._compare_ids)))
        self._refresh_table()


# ─────────────────────────── Run detail screen ───────────────────────────────

class RunDetailScreen(Screen):
    BINDINGS = [
        Binding("escape,q", "pop_screen", "Back"),
        Binding("s", "stop_run", "Stop"),
        Binding("r", "resume_run", "Resume"),
        Binding("e", "toggle_errors", "Toggle errors"),
    ]

    def __init__(self, run: RunRecord, procs: dict, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._run = run
        self._procs = procs
        self._jsonl_offset = 0
        self._all_instances: list[models.InstanceRecord] = []
        self._error_only = False
        self._page = 0
        self._page_size = 50

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Static(id="run_header")
            yield ProgressBar(id="progress_bar", total=100, show_eta=False)
            with Horizontal(id="metrics_row"):
                yield Static(id="m_done", classes="metric")
                yield Static(id="m_errors", classes="metric")
                yield Static(id="m_recall", classes="metric")
                yield Static(id="m_mrr", classes="metric")
                yield Static(id="m_throughput", classes="metric")
                yield Static(id="m_eta", classes="metric")
            with Horizontal(id="controls"):
                yield Button("Stop", id="btn_stop", variant="error")
                yield Button("Resume", id="btn_resume", variant="success")
                yield Button("Open Report", id="btn_report", variant="default")
            with Horizontal():
                with Vertical(id="log_panel"):
                    yield Label("Log tail")
                    yield Log(id="run_log", highlight=True)
                with Vertical(id="instances_panel"):
                    yield Label("Instances (press E to toggle errors only)")
                    yield DataTable(id="instances_table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#instances_table", DataTable)
        table.add_columns("Instance ID", "Repo", "R@5", "R@10", "MRR", "Seeds", "Time", "Error")
        self._update_controls()
        self._refresh()
        self.set_interval(2, self._refresh)

    def _update_controls(self) -> None:
        run = state.get_run(self._run.id) or self._run
        is_running = run.status == "running"
        self.query_one("#btn_stop", Button).disabled = not is_running
        self.query_one("#btn_resume", Button).disabled = is_running or run.status == "completed"
        self.query_one("#run_header", Static).update(
            f"[bold]{run.id}[/bold]  {_styled_status(run.status)}"
        )

    def _refresh(self) -> None:
        run = state.get_run(self._run.id) or self._run
        jsonl = Path(run.output_dir) / "per_instance.jsonl"
        new_instances, self._jsonl_offset = parser.read_instances(jsonl, self._jsonl_offset)
        self._all_instances.extend(new_instances)

        started = datetime.fromisoformat(run.started_at) if run.started_at else datetime.now()
        prog = parser.compute_live_progress(self._all_instances, started, None)

        # Update progress bar
        pbar = self.query_one("#progress_bar", ProgressBar)
        if prog.n_total and prog.n_total > 0:
            pbar.total = prog.n_total
            pbar.progress = prog.n_done
        else:
            pbar.total = max(prog.n_done, 1)
            pbar.progress = prog.n_done

        # Update metric labels
        self.query_one("#m_done", Static).update(f"Done: {prog.n_done}")
        self.query_one("#m_errors", Static).update(f"Errors: {prog.n_errors}")
        self.query_one("#m_recall", Static).update(f"R@10: {_fmt_metric(prog.mean_recall_at_10)}")
        self.query_one("#m_mrr", Static).update(f"MRR: {_fmt_metric(prog.mean_mrr)}")
        self.query_one("#m_throughput", Static).update(f"Thru: {_fmt_throughput(prog.throughput_per_hour)}")
        self.query_one("#m_eta", Static).update(f"ETA: {_fmt_eta(prog.eta_seconds)}")

        # Update log tail
        log_widget = self.query_one("#run_log", Log)
        log_path = Path(run.output_dir) / "run.log"
        lines = parser.read_log_tail(log_path, n_lines=100)
        if lines:
            log_widget.clear()
            for line in lines:
                log_widget.write_line(line)

        # Append new instance rows
        if new_instances:
            table = self.query_one("#instances_table", DataTable)
            for inst in new_instances:
                if self._error_only and inst.error is None:
                    continue
                table.add_row(
                    inst.instance_id,
                    inst.repo,
                    _fmt_metric(inst.recall_at_5),
                    _fmt_metric(inst.recall_at_10),
                    _fmt_metric(inst.mrr),
                    str(inst.n_seeds),
                    f"{inst.elapsed_seconds:.1f}s",
                    (inst.error or "")[:50],
                    key=inst.instance_id,
                )

        self._update_controls()

    def action_stop_run(self) -> None:
        proc = self._procs.get(self._run.id)
        if proc:
            asyncio.create_task(runner.stop_run(proc))

    def action_resume_run(self) -> None:
        run = state.get_run(self._run.id) or self._run
        if run.config:
            self.app.push_screen(ResumeScreen(run))

    def action_toggle_errors(self) -> None:
        self._error_only = not self._error_only
        table = self.query_one("#instances_table", DataTable)
        table.clear()
        for inst in self._all_instances:
            if self._error_only and inst.error is None:
                continue
            table.add_row(
                inst.instance_id, inst.repo,
                _fmt_metric(inst.recall_at_5), _fmt_metric(inst.recall_at_10),
                _fmt_metric(inst.mrr), str(inst.n_seeds),
                f"{inst.elapsed_seconds:.1f}s", (inst.error or "")[:50],
                key=inst.instance_id,
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_stop":
            self.action_stop_run()
        elif event.button.id == "btn_resume":
            self.action_resume_run()
        elif event.button.id == "btn_report":
            self._open_report()

    def _open_report(self) -> None:
        run = state.get_run(self._run.id) or self._run
        report_path = Path(run.output_dir) / "index.html"
        if not report_path.exists():
            import subprocess as sp
            sp.Popen(
                ["python", "evaluation/report.py", run.output_dir],
                stdout=sp.DEVNULL, stderr=sp.DEVNULL,
            )
        webbrowser.open(report_path.as_uri())


# ─────────────────────────── New run screen ──────────────────────────────────

_RETRIEVERS = [("ppr", "ppr"), ("bm25", "bm25"), ("random", "random"), ("one_hop", "one_hop")]
_GROUPINGS = [("repo_commit", "repo_commit"), ("none", "none")]


def _ablation_options() -> list[tuple[str, str]]:
    try:
        from evaluation.ablations import ABLATIONS
        return [(a.name, a.name) for a in ABLATIONS]
    except Exception:
        return [("baseline", "baseline")]


class NewRunScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def compose(self) -> ComposeResult:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_out = str(_RESULTS_ROOT / f"run_{ts}")
        with Container(id="new_run_form"):
            yield Label("New Evaluation Run", id="form_title")
            yield Label("Output directory")
            yield Input(value=default_out, id="input_output_dir")
            yield Label("Retriever")
            yield Select(_RETRIEVERS, value="ppr", id="sel_retriever")
            yield Label("Ablation")
            yield Select(_ablation_options(), value="baseline", id="sel_ablation")
            yield Label("Grouping")
            yield Select(_GROUPINGS, value="repo_commit", id="sel_grouping")
            yield Label("Limit (0 = all)")
            yield Input(value="0", id="input_limit")
            yield Label("Config path")
            yield Input(value="config.yaml", id="input_config")
            yield Label("Cache dir")
            yield Input(value=".codegraph_cache/repos", id="input_cache")
            with Horizontal():
                yield Button("Start", id="btn_start", variant="success")
                yield Button("Cancel", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss()
            return
        if event.button.id != "btn_start":
            return

        output_dir = self.query_one("#input_output_dir", Input).value.strip()
        retriever = str(self.query_one("#sel_retriever", Select).value)
        ablation = str(self.query_one("#sel_ablation", Select).value)
        grouping = str(self.query_one("#sel_grouping", Select).value)
        limit_str = self.query_one("#input_limit", Input).value.strip()
        config_path = self.query_one("#input_config", Input).value.strip()
        cache_dir = self.query_one("#input_cache", Input).value.strip()

        try:
            limit = int(limit_str)
        except ValueError:
            limit = 0

        config = RunConfig(
            output_dir=output_dir,
            retriever=retriever,
            ablation=ablation,
            grouping=grouping,
            limit=limit,
            config_path=config_path,
            cache_dir=cache_dir,
        )
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = Path(output_dir).name or f"run_{ts}"
        self.dismiss((run_id, config))


# ─────────────────────────── Resume screen ───────────────────────────────────

class ResumeScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, run: RunRecord, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._run = run

    def compose(self) -> ComposeResult:
        with Container(id="resume_form"):
            yield Label(f"Resume: {self._run.id}")
            yield Label("Retry previously errored instances?")
            yield Select(
                [("No", "no"), ("Yes", "yes")], value="no", id="sel_retry"
            )
            with Horizontal():
                yield Button("Resume", id="btn_resume", variant="success")
                yield Button("Cancel", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss()
        elif event.button.id == "btn_resume":
            retry = str(self.query_one("#sel_retry", Select).value) == "yes"
            self.dismiss((self._run, retry))


# ─────────────────────────── Compare screen ──────────────────────────────────

class CompareScreen(Screen):
    BINDINGS = [Binding("escape,q", "pop_screen", "Back")]

    def __init__(self, run_ids: list[str], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._run_ids = run_ids

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Run Comparison")
        yield DataTable(id="compare_table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#compare_table", DataTable)
        table.add_columns(
            "Run ID", "Status", "Retriever", "Ablation",
            "N", "R@5", "R@10", "MRR", "Errors"
        )
        import json as _json

        for run_id in self._run_ids:
            run = state.get_run(run_id)
            if not run:
                continue

            # Try to load summary.json for final metrics
            summary_path = Path(run.output_dir) / "summary.json"
            if summary_path.exists():
                try:
                    with open(summary_path) as f:
                        s = _json.load(f)
                    n = s.get("n_instances", "—")
                    r5 = _fmt_metric(s.get("mean_recall_at_5", 0.0))
                    r10 = _fmt_metric(s.get("mean_recall_at_10", 0.0))
                    mrr = _fmt_metric(s.get("mean_mrr", 0.0))
                    errors = str(s.get("instances_with_zero_recall", "—"))
                except Exception:
                    n = r5 = r10 = mrr = errors = "—"
            else:
                # Fall back to live JSONL parse
                jsonl = Path(run.output_dir) / "per_instance.jsonl"
                instances, _ = parser.read_instances(jsonl)
                started = datetime.fromisoformat(run.started_at) if run.started_at else datetime.now()
                prog = parser.compute_live_progress(instances, started, None)
                n = str(prog.n_done)
                r5 = "—"
                r10 = _fmt_metric(prog.mean_recall_at_10)
                mrr = _fmt_metric(prog.mean_mrr)
                errors = str(prog.n_errors)

            cfg = run.config
            table.add_row(
                run_id,
                _styled_status(run.status),
                cfg.retriever if cfg else "—",
                cfg.ablation if cfg else "—",
                str(n), r5, r10, mrr, errors,
                key=run_id,
            )


# ─────────────────────────── Main App ────────────────────────────────────────

class BenchDashboard(App):
    CSS = """
    Screen { layers: below above; }

    #runs_table { height: 1fr; }

    RunDetailScreen > Vertical { height: 1fr; }
    #metrics_row { height: 3; }
    .metric { width: 1fr; content-align: center middle; border: solid $panel; }
    #controls { height: 3; }
    #log_panel { width: 1fr; height: 1fr; border: solid $panel; }
    #instances_panel { width: 2fr; height: 1fr; border: solid $panel; }
    #run_log { height: 1fr; }

    #new_run_form, #resume_form {
        align: center middle;
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #form_title { text-align: center; text-style: bold; margin-bottom: 1; }

    #compare_table { height: 1fr; }
    """

    TITLE = "SWE-bench Evaluation Dashboard"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Active process registry: run_id -> asyncio.subprocess.Process
        self._procs: dict[str, asyncio.subprocess.Process] = {}

    def on_mount(self) -> None:
        # Discover existing runs from filesystem
        state.discover_existing_runs(_RESULTS_ROOT)
        self.push_screen(RunsScreen())

    async def on_new_run_screen_dismiss(self, event) -> None:
        """Handle NewRunScreen result."""
        result = event.result
        if result is None:
            return
        run_id, config = result
        now = datetime.now().isoformat()
        record = RunRecord(
            id=run_id,
            output_dir=config.output_dir,
            status="running",
            started_at=now,
            config=config,
        )
        state.upsert_run(record)
        proc = await runner.start_run(config, run_id)
        self._procs[run_id] = proc
        record.pid = proc.pid
        state.upsert_run(record)
        # Watch process in background
        asyncio.create_task(self._watch_proc(run_id, proc))

    async def on_resume_screen_dismiss(self, event) -> None:
        """Handle ResumeScreen result."""
        result = event.result
        if result is None:
            return
        run, retry_errors = result
        if not run.config:
            return
        run.status = "running"
        run.started_at = datetime.now().isoformat()
        state.upsert_run(run)
        proc = await runner.resume_run(run.config, run.id, retry_errors=retry_errors)
        self._procs[run.id] = proc
        run.pid = proc.pid
        state.upsert_run(run)
        asyncio.create_task(self._watch_proc(run.id, proc))

    async def _watch_proc(self, run_id: str, proc: asyncio.subprocess.Process) -> None:
        """Wait for process to exit and update run status accordingly."""
        exit_code = await proc.wait()
        self._procs.pop(run_id, None)
        run = state.get_run(run_id)
        if run:
            run.status = "completed" if exit_code == 0 else "failed"
            run.finished_at = datetime.now().isoformat()
            run.exit_code = exit_code
            state.upsert_run(run)


def main() -> None:
    """CLI entrypoint for codegraph-bench-dashboard."""
    import argparse
    ap = argparse.ArgumentParser(description="SWE-bench evaluation dashboard")
    ap.add_argument("--results-dir", default=str(_RESULTS_ROOT),
                    help="Path to evaluation results directory")
    args = ap.parse_args()

    results_root = Path(args.results_dir)

    class _App(BenchDashboard):
        def on_mount(self) -> None:
            state.discover_existing_runs(results_root)
            self.push_screen(RunsScreen())

    _App().run()


if __name__ == "__main__":
    main()
