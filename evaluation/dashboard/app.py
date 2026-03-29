"""SWE-bench evaluation dashboard - Textual TUI."""
from __future__ import annotations

import asyncio
import webbrowser
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
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
from evaluation.dashboard import parser, runner, state
from evaluation.dashboard.config import normalize_and_validate_config
from evaluation.dashboard.models import RunConfig, RunRecord

_RESULTS_ROOT = Path(__file__).parent.parent / "results"

_DEFAULT_QUICK_LIMIT = 5
_QUICK_RETRIEVER = "ppr"
_QUICK_ABLATION = "baseline"
_QUICK_GROUPING = "repo_commit"
_QUICK_CONFIG_PATH = "config.yaml"
_QUICK_CACHE_DIR = ".codegraph_cache/repos"

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


def _fmt_metric(value: float) -> str:
    return f"{value:.3f}"


def _fmt_eta(eta: float | None) -> str:
    if eta is None:
        return "-"
    hours, rem = divmod(int(eta), 3600)
    mins, secs = divmod(rem, 60)
    return f"{hours}h{mins:02d}m" if hours else f"{mins}m{secs:02d}s"


def _fmt_throughput(value: float) -> str:
    return f"{value:.1f}/hr" if value > 0 else "-"


def _short(text: str | None, max_len: int = 72) -> str:
    if not text:
        return "-"
    return text if len(text) <= max_len else f"{text[: max_len - 1]}..."


def _ablation_options() -> list[tuple[str, str]]:
    try:
        from evaluation.ablations import ABLATIONS

        return [(a.name, a.name) for a in ABLATIONS]
    except Exception:
        return [("baseline", "baseline")]


class RunsScreen(Screen):
    BINDINGS = [
        Binding("p", "quick_run", "Quick Run"),
        Binding("n", "new_run", "Advanced Run"),
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
        with Horizontal(id="runs_actions"):
            yield Button("Quick Run (PPR pilot)", id="btn_quick_run", variant="success")
            yield Button("Advanced Run...", id="btn_new_run")
            yield Static("Default pilot limit: 5", id="runs_hint")
        yield DataTable(id="runs_table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#runs_table", DataTable)
        table.add_columns(
            "ID",
            "Status",
            "Retriever",
            "Ablation",
            "Done",
            "R@10",
            "MRR",
            "Started",
            "Details",
        )
        self._refresh_table()
        self.set_interval(3, self._refresh_table)

    def _refresh_table(self) -> None:
        table = self.query_one("#runs_table", DataTable)
        runs = state.list_runs()
        cursor_row = table.cursor_row

        table.clear()
        for run in runs:
            jsonl = Path(run.output_dir) / "per_instance.jsonl"
            instances, _ = parser.read_instances(jsonl)
            started = datetime.fromisoformat(run.started_at) if run.started_at else datetime.now()
            prog = parser.compute_live_progress(instances, started, None)

            marker = "* " if run.id in self._compare_ids else "  "
            cfg = run.config
            retriever = cfg.retriever if cfg else "-"
            ablation = cfg.ablation if cfg else "-"
            started_str = run.started_at[:16] if run.started_at else "-"

            detail = "-"
            if run.status == "failed":
                detail = _short(run.last_error_summary or f"exit={run.exit_code}")
            elif run.status == "stopped":
                detail = _short(run.last_error_summary or "Stopped by user")

            table.add_row(
                f"{marker}{run.id}",
                _styled_status(run.status),
                retriever,
                ablation,
                str(prog.n_done),
                _fmt_metric(prog.mean_recall_at_10),
                _fmt_metric(prog.mean_mrr),
                started_str,
                detail,
                key=run.id,
            )

        if cursor_row is not None and cursor_row < table.row_count:
            table.move_cursor(row=cursor_row)

    def _selected_run_id(self) -> str | None:
        table = self.query_one("#runs_table", DataTable)
        if table.row_count == 0:
            return None
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return str(row_key.value) if row_key.value else None

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter on a DataTable row (DataTable consumes Enter before Screen bindings)."""
        run_id = str(event.row_key.value) if event.row_key.value else None
        if not run_id:
            return
        run = state.get_run(run_id)
        if run:
            self.app.push_screen(RunDetailScreen(run, self.app._procs))

    def action_view_detail(self) -> None:
        run_id = self._selected_run_id()
        if not run_id:
            return
        run = state.get_run(run_id)
        if run:
            self.app.push_screen(RunDetailScreen(run, self.app._procs))

    def action_stop_run(self) -> None:
        run_id = self._selected_run_id()
        if not run_id:
            return
        self.app.request_stop(run_id)

    def action_resume_run(self) -> None:
        run_id = self._selected_run_id()
        if not run_id:
            return
        run = state.get_run(run_id)
        if run:
            self.app.open_resume_screen(run)

    def action_new_run(self) -> None:
        self.app.push_screen(NewRunScreen(), self.app._on_new_run_result)

    def action_quick_run(self) -> None:
        self.app.push_screen(QuickRunScreen(), self.app._on_quick_run_result)

    def action_toggle_compare(self) -> None:
        run_id = self._selected_run_id()
        if not run_id:
            return
        if run_id in self._compare_ids:
            self._compare_ids.discard(run_id)
        else:
            self._compare_ids.add(run_id)
        if len(self._compare_ids) >= 2:
            self.app.push_screen(CompareScreen(list(self._compare_ids)))
        self._refresh_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_quick_run":
            self.action_quick_run()
        elif event.button.id == "btn_new_run":
            self.action_new_run()


class RunDetailScreen(Screen):
    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("q", "pop_screen", "Back"),
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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield Static(id="run_header")
            yield Static(id="run_diag")
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
                    yield Label("Log tail (last 200 lines)")
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

        suffix = f"  (exit={run.exit_code})" if run.exit_code is not None else ""
        self.query_one("#run_header", Static).update(
            f"[bold]{run.id}[/bold]  {_styled_status(run.status)}{suffix}"
        )

        diag_parts: list[str] = []
        if run.last_command:
            diag_parts.append(f"Command: {run.last_command}")
        if run.last_error_summary:
            diag_parts.append(f"Failure: {run.last_error_summary}")
        self.query_one("#run_diag", Static).update("\n".join(diag_parts) if diag_parts else "")

    def _refresh(self) -> None:
        run = state.get_run(self._run.id) or self._run

        jsonl = Path(run.output_dir) / "per_instance.jsonl"
        new_instances, self._jsonl_offset = parser.read_instances(jsonl, self._jsonl_offset)
        self._all_instances.extend(new_instances)

        started = datetime.fromisoformat(run.started_at) if run.started_at else datetime.now()
        prog = parser.compute_live_progress(self._all_instances, started, None)

        pbar = self.query_one("#progress_bar", ProgressBar)
        if prog.n_total and prog.n_total > 0:
            pbar.total = prog.n_total
            pbar.progress = prog.n_done
        else:
            pbar.total = max(prog.n_done, 1)
            pbar.progress = prog.n_done

        self.query_one("#m_done", Static).update(f"Done: {prog.n_done}")
        self.query_one("#m_errors", Static).update(f"Errors: {prog.n_errors}")
        self.query_one("#m_recall", Static).update(f"R@10: {_fmt_metric(prog.mean_recall_at_10)}")
        self.query_one("#m_mrr", Static).update(f"MRR: {_fmt_metric(prog.mean_mrr)}")
        self.query_one("#m_throughput", Static).update(f"Thru: {_fmt_throughput(prog.throughput_per_hour)}")
        self.query_one("#m_eta", Static).update(f"ETA: {_fmt_eta(prog.eta_seconds)}")

        log_widget = self.query_one("#run_log", Log)
        log_path = Path(run.output_dir) / "run.log"
        lines = parser.read_log_tail(log_path, n_lines=200)
        log_widget.clear()
        for line in lines:
            log_widget.write_line(line)

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
                    (inst.error or "")[:80],
                    key=inst.instance_id,
                )

        self._update_controls()

    def action_stop_run(self) -> None:
        self.app.request_stop(self._run.id)

    def action_resume_run(self) -> None:
        run = state.get_run(self._run.id) or self._run
        self.app.open_resume_screen(run)

    def action_toggle_errors(self) -> None:
        self._error_only = not self._error_only
        table = self.query_one("#instances_table", DataTable)
        table.clear()
        for inst in self._all_instances:
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
                (inst.error or "")[:80],
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
                stdout=sp.DEVNULL,
                stderr=sp.DEVNULL,
            )
        webbrowser.open(report_path.as_uri())


_RETRIEVERS = [("ppr", "ppr"), ("bm25", "bm25"), ("random", "random"), ("one_hop", "one_hop")]
_GROUPINGS = [("repo_commit", "repo_commit"), ("none", "none")]


class QuickRunScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def compose(self) -> ComposeResult:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_out = str(_RESULTS_ROOT / f"quick_ppr_{ts}")
        with Container(id="quick_run_form"):
            yield Label("Quick PPR Pilot", id="form_title")
            yield Label("Output directory")
            yield Input(value=default_out, id="quick_output_dir")
            yield Label("Limit (default 5)")
            yield Input(value=str(_DEFAULT_QUICK_LIMIT), id="quick_limit")
            with Horizontal():
                yield Button("Run", id="btn_quick_start", variant="success")
                yield Button("Cancel", id="btn_quick_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_quick_cancel":
            self.dismiss()
            return
        if event.button.id != "btn_quick_start":
            return

        output_dir = self.query_one("#quick_output_dir", Input).value.strip()
        limit_str = self.query_one("#quick_limit", Input).value.strip()

        try:
            limit = int(limit_str)
        except ValueError:
            limit = _DEFAULT_QUICK_LIMIT

        config = RunConfig(
            output_dir=output_dir,
            retriever=_QUICK_RETRIEVER,
            ablation=_QUICK_ABLATION,
            grouping=_QUICK_GROUPING,
            limit=limit,
            config_path=_QUICK_CONFIG_PATH,
            cache_dir=_QUICK_CACHE_DIR,
        )
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = Path(output_dir).name or f"quick_ppr_{ts}"
        self.dismiss((run_id, config))


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
        retriever = self.query_one("#sel_retriever", Select).value
        ablation = self.query_one("#sel_ablation", Select).value
        grouping = self.query_one("#sel_grouping", Select).value

        if retriever is Select.BLANK:
            retriever = "ppr"
        if ablation is Select.BLANK:
            ablation = "baseline"
        if grouping is Select.BLANK:
            grouping = "repo_commit"

        limit_str = self.query_one("#input_limit", Input).value.strip()
        config_path = self.query_one("#input_config", Input).value.strip()
        cache_dir = self.query_one("#input_cache", Input).value.strip()

        try:
            limit = int(limit_str)
        except ValueError:
            limit = 0

        config = RunConfig(
            output_dir=output_dir,
            retriever=str(retriever),
            ablation=str(ablation),
            grouping=str(grouping),
            limit=limit,
            config_path=config_path,
            cache_dir=cache_dir,
        )
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = Path(output_dir).name or f"run_{ts}"
        self.dismiss((run_id, config))


class ResumeScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, run: RunRecord, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._run = run

    def compose(self) -> ComposeResult:
        with Container(id="resume_form"):
            yield Label(f"Resume: {self._run.id}")
            yield Label("Retry previously errored instances?")
            yield Select([("No", "no"), ("Yes", "yes")], value="no", id="sel_retry")
            with Horizontal():
                yield Button("Resume", id="btn_resume", variant="success")
                yield Button("Cancel", id="btn_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_cancel":
            self.dismiss()
        elif event.button.id == "btn_resume":
            val = self.query_one("#sel_retry", Select).value
            retry = str(val) == "yes" if val is not Select.BLANK else False
            self.dismiss((self._run, retry))


class CompareScreen(Screen):
    BINDINGS = [Binding("escape", "pop_screen", "Back"), Binding("q", "pop_screen", "Back")]

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
        table.add_columns("Run ID", "Status", "Retriever", "Ablation", "N", "R@5", "R@10", "MRR", "Errors")

        import json as _json

        for run_id in self._run_ids:
            run = state.get_run(run_id)
            if not run:
                continue

            summary_path = Path(run.output_dir) / "summary.json"
            if summary_path.exists():
                try:
                    with open(summary_path, encoding="utf-8") as file_handle:
                        summary = _json.load(file_handle)
                    n = summary.get("n_instances", "-")
                    r5 = _fmt_metric(summary.get("mean_recall_at_5", 0.0))
                    r10 = _fmt_metric(summary.get("mean_recall_at_10", 0.0))
                    mrr = _fmt_metric(summary.get("mean_mrr", 0.0))
                    errors = str(summary.get("instances_with_zero_recall", "-"))
                except Exception:
                    n = r5 = r10 = mrr = errors = "-"
            else:
                jsonl = Path(run.output_dir) / "per_instance.jsonl"
                instances, _ = parser.read_instances(jsonl)
                started = datetime.fromisoformat(run.started_at) if run.started_at else datetime.now()
                prog = parser.compute_live_progress(instances, started, None)
                n = str(prog.n_done)
                r5 = "-"
                r10 = _fmt_metric(prog.mean_recall_at_10)
                mrr = _fmt_metric(prog.mean_mrr)
                errors = str(prog.n_errors)

            cfg = run.config
            table.add_row(
                run_id,
                _styled_status(run.status),
                cfg.retriever if cfg else "-",
                cfg.ablation if cfg else "-",
                str(n),
                r5,
                r10,
                mrr,
                errors,
                key=run_id,
            )


class BenchDashboard(App):
    CSS = """
    Screen { layers: below above; }

    #runs_actions { height: 3; margin: 0 1; }
    #runs_hint { content-align: left middle; width: 1fr; }
    #runs_table { height: 1fr; }

    RunDetailScreen > Vertical { height: 1fr; }
    #run_diag { height: auto; color: $text-muted; margin: 0 1; }
    #metrics_row { height: 3; }
    .metric { width: 1fr; content-align: center middle; border: solid $panel; }
    #controls { height: 3; }
    #log_panel { width: 1fr; height: 1fr; border: solid $panel; }
    #instances_panel { width: 2fr; height: 1fr; border: solid $panel; }
    #run_log { height: 1fr; }

    #quick_run_form, #new_run_form, #resume_form {
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
        self._procs: dict[str, asyncio.subprocess.Process] = {}
        self._stop_requested: set[str] = set()

    def on_mount(self) -> None:
        state.discover_existing_runs(_RESULTS_ROOT)
        self.push_screen(RunsScreen())

    def _notify(self, message: str, *, severity: str = "information") -> None:
        try:
            self.notify(message, severity=severity)
        except Exception:
            pass

    def _normalize_config(self, config: RunConfig | None, *, output_dir: str | None = None) -> tuple[RunConfig | None, str | None]:
        checked = normalize_and_validate_config(config, output_dir_fallback=output_dir)
        for warning in checked.warnings:
            self._notify(warning, severity="warning")
        if checked.errors:
            reason = " ".join(checked.errors)
            return None, reason
        return checked.config, None

    def open_resume_screen(self, run: RunRecord) -> None:
        normalized, reason = self._normalize_config(run.config, output_dir=run.output_dir)
        if reason:
            run.last_error_summary = f"Resume blocked: {reason}"
            state.upsert_run(run)
            self._notify(run.last_error_summary, severity="error")
            return
        if normalized is None:
            run.last_error_summary = "Resume blocked: could not normalize run config."
            state.upsert_run(run)
            self._notify(run.last_error_summary, severity="error")
            return
        run.config = normalized
        state.upsert_run(run)
        self.push_screen(ResumeScreen(run), self._on_resume_result)

    def request_stop(self, run_id: str) -> None:
        proc = self._procs.get(run_id)
        if not proc:
            self._notify(f"Run {run_id} is not currently active.", severity="warning")
            return
        self._stop_requested.add(run_id)
        asyncio.create_task(runner.stop_run(proc))

    async def _start_run(self, run_id: str, config: RunConfig) -> None:
        normalized, reason = self._normalize_config(config, output_dir=config.output_dir)

        now = datetime.now().isoformat()
        if reason or normalized is None:
            record = RunRecord(
                id=run_id,
                output_dir=config.output_dir,
                status="failed",
                started_at=now,
                finished_at=now,
                config=config,
                exit_code=1,
                last_error_summary=reason or "Invalid run configuration.",
            )
            state.upsert_run(record)
            self._notify(record.last_error_summary or "Failed to start run.", severity="error")
            return

        record = RunRecord(
            id=run_id,
            output_dir=normalized.output_dir,
            status="running",
            started_at=now,
            config=normalized,
            last_error_summary=None,
            last_command=None,
        )
        state.upsert_run(record)

        try:
            launch = await runner.start_run(normalized, run_id)
        except Exception as exc:
            record.status = "failed"
            record.finished_at = datetime.now().isoformat()
            record.exit_code = 1
            record.last_error_summary = f"Failed to start process: {exc}"
            state.upsert_run(record)
            self._notify(record.last_error_summary, severity="error")
            return

        self._procs[run_id] = launch.process
        record.pid = launch.process.pid
        record.last_command = launch.command_display
        state.upsert_run(record)
        asyncio.create_task(self._watch_proc(run_id, launch.process))

    async def _on_quick_run_result(self, result) -> None:
        if result is None:
            return
        run_id, config = result
        await self._start_run(run_id, config)

    async def _on_new_run_result(self, result) -> None:
        if result is None:
            return
        run_id, config = result
        await self._start_run(run_id, config)

    async def _on_resume_result(self, result) -> None:
        if result is None:
            return

        run, retry_errors = result
        normalized, reason = self._normalize_config(run.config, output_dir=run.output_dir)
        if reason or normalized is None:
            run.last_error_summary = f"Resume blocked: {reason or 'invalid launch config.'}"
            state.upsert_run(run)
            self._notify(run.last_error_summary, severity="error")
            return

        run.config = normalized
        run.status = "running"
        run.started_at = datetime.now().isoformat()
        run.finished_at = None
        run.exit_code = None
        run.last_error_summary = None
        state.upsert_run(run)

        try:
            launch = await runner.resume_run(normalized, run.id, retry_errors=retry_errors)
        except Exception as exc:
            run.status = "failed"
            run.finished_at = datetime.now().isoformat()
            run.exit_code = 1
            run.last_error_summary = f"Failed to resume process: {exc}"
            state.upsert_run(run)
            self._notify(run.last_error_summary, severity="error")
            return

        self._procs[run.id] = launch.process
        run.pid = launch.process.pid
        run.last_command = launch.command_display
        state.upsert_run(run)
        asyncio.create_task(self._watch_proc(run.id, launch.process))

    async def _watch_proc(self, run_id: str, proc: asyncio.subprocess.Process) -> None:
        exit_code = await proc.wait()

        log_handle = getattr(proc, "_dashboard_log_file", None)
        if log_handle is not None:
            try:
                log_handle.close()
            except Exception:
                pass

        self._procs.pop(run_id, None)

        stop_requested = run_id in self._stop_requested
        self._stop_requested.discard(run_id)

        run = state.get_run(run_id)
        if not run:
            return

        run.finished_at = datetime.now().isoformat()
        run.exit_code = exit_code

        if stop_requested:
            run.status = "stopped"
            run.last_error_summary = "Stopped by user"
        elif exit_code == 0:
            run.status = "completed"
            run.last_error_summary = None
        else:
            run.status = "failed"
            log_path = Path(run.output_dir) / "run.log"
            run.last_error_summary = parser.summarize_failure(log_path, exit_code, n_lines=200)
            self._notify(f"Run {run.id} failed: {_short(run.last_error_summary, max_len=120)}", severity="error")

        state.upsert_run(run)


def main() -> None:
    """CLI entrypoint for codegraph-bench-dashboard."""
    import argparse

    arg_parser = argparse.ArgumentParser(description="SWE-bench evaluation dashboard")
    arg_parser.add_argument(
        "--results-dir",
        default=str(_RESULTS_ROOT),
        help="Path to evaluation results directory",
    )
    args = arg_parser.parse_args()

    results_root = Path(args.results_dir)

    class _App(BenchDashboard):
        def on_mount(self) -> None:
            state.discover_existing_runs(results_root)
            self.push_screen(RunsScreen())

    _App().run()


if __name__ == "__main__":
    main()
