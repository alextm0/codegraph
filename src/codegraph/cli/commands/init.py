"""Init command helper."""

from __future__ import annotations

from pathlib import Path

from rich.prompt import Confirm, Prompt

from codegraph.utils.config import resolve_project_root, save_raw_config

from codegraph.cli.commands._shared import console
from codegraph.cli.commands.build import rebuild_helper


def init_helper(config_path: Path, target: str | None = None) -> None:
    """Run an interactive setup wizard to create/update config.yaml and clone/index."""
    import subprocess

    console.print("\n[bold cyan]CodeGraph Setup Wizard[/bold cyan]\n")

    if not target:
        target = Prompt.ask(
            "[bold blue]Enter a local folder path or GitHub URL to index[/bold blue]",
            default=".",
        )

    project_root = "."
    if target.startswith("http://") or target.startswith("https://"):
        repo_name = target.rstrip("/").split("/")[-1].replace(".git", "")
        clone_path = Path.cwd() / repo_name
        console.print(
            f"\n[bold yellow]Cloning {target} into {clone_path}...[/bold yellow]"
        )
        try:
            subprocess.run(["git", "clone", target, str(clone_path)], check=True)
            project_root = str(clone_path)
            console.print("   [green]+[/green] Cloned successfully!")
        except subprocess.CalledProcessError as e:
            console.print(f"   [red]-[/red] Clone failed: {e}")
            return
    else:
        project_root = str(Path(target).resolve())

    if config_path.exists():
        if not Confirm.ask(
            f"\nConfig file [blue]{config_path.name}[/blue] already exists. Overwrite?"
        ):
            return

    # 1. Neo4j Settings
    console.print("\n[bold]1. Database Connection[/bold]")
    console.print("   [dim]CodeGraph requires Neo4j 5.x with the GDS plugin.[/dim]")
    console.print(
        "   [dim]Download: https://neo4j.com/deployment-center/ (Community Edition is free)[/dim]\n"
    )
    uri = Prompt.ask("Neo4j URI", default="neo4j://localhost:7687")
    user = Prompt.ask("Neo4j Username", default="neo4j")
    password = Prompt.ask("Neo4j Password", password=True)

    # Test connectivity
    connected = False
    with console.status("[yellow]Testing connectivity..."):
        try:
            from codegraph.core.graph.connection import Neo4jConfig
            from codegraph.core.graph.database import DatabaseManager

            test_config = Neo4jConfig(
                uri=uri, username=user, password=password, database="neo4j"
            )
            test_mgr = DatabaseManager()
            test_mgr._config = test_config
            connected = test_mgr.is_connected()
        except Exception:
            connected = False

    if connected:
        console.print("   [green]+[/green] Connected successfully!")
    else:
        console.print("   [red]-[/red] Connection failed.")
        console.print(
            "   [dim]Make sure Neo4j is running: check Neo4j Desktop or run 'neo4j start'[/dim]"
        )
        console.print("   [dim]Then verify credentials at http://localhost:7474[/dim]")
        if not Confirm.ask("Continue and save config anyway?"):
            return

    # 2. Project Settings
    console.print("\n[bold]2. Project Settings[/bold]")

    # We already have project_root from the target, but let user confirm
    project_root = Prompt.ask(
        "Project root directory (absolute or relative to config)", default=project_root
    )
    resolved = (
        (config_path.parent / project_root).resolve()
        if not Path(project_root).is_absolute()
        else Path(project_root)
    )
    if not resolved.exists():
        console.print(f"   [red]-[/red] Directory not found: {resolved}")
        if not Confirm.ask("Use it anyway?"):
            return

    # 3. Exclude Patterns
    exclude = [
        ".git",
        "__pycache__",
        ".venv",
        "node_modules",
        ".pytest_cache",
        "tests/fixtures/",
    ]
    console.print(
        f"\n[bold]3. Default exclusions:[/bold] [dim]{', '.join(exclude)}[/dim]"
    )

    # Write password to .env, not config.yaml
    env_file = config_path.parent / ".env"
    _write_env_password(env_file, password)
    console.print(
        f"   [green]+[/green] Password written to [blue]{env_file.name}[/blue] (not stored in config.yaml)"
    )

    config_data = {
        "neo4j": {
            "uri": uri,
            "username": user,
        },
        "project_root": project_root,
        "exclude_patterns": exclude,
        "ppr": {
            "damping_factor": 0.70,
            "max_iterations": 20,
            "tolerance": 1.0e-7,
            "top_k": 30,
            "retrieval_mode": "uniform",
        },
        "seed_selection": {
            "entity_match_weight": 0.6,
            "bm25_weight": 0.3,
            "bm25_top_n": 10,
            "exclude_seed_paths": ["tests/", "test_"],
        },
        "mcp": {
            "server_name": "codegraph",
            "default_token_budget": 6000,
            "default_top_k": 30,
        },
    }

    save_raw_config(config_path, config_data)
    console.print(f"\n[bold green]+ Configuration saved to {config_path}[/bold green]")

    # Create .cgignore if it doesn't exist
    resolved_root = resolve_project_root(config_data, config_path)
    ignore_file = resolved_root / ".cgignore"
    if not ignore_file.exists():
        if Confirm.ask("Create [blue].cgignore[/blue] with default patterns?"):
            with open(ignore_file, "w", encoding="utf-8") as f:
                f.write("# CodeGraph ignore patterns\n")
                for p in exclude:
                    f.write(f"{p}\n")
            console.print(f"   [green]+[/green] Created {ignore_file}")

    if target and (target.startswith("http://") or target.startswith("https://")):
        console.print(f"\n[bold green]Auto-indexing {project_root}...[/bold green]")
        rebuild_helper(config_path)
    else:
        if Confirm.ask("\nRun [bold]codegraph rebuild[/bold] now?", default=True):
            rebuild_helper(config_path)


def _write_env_password(env_file: Path, password: str) -> None:
    """Write NEO4J_PASSWORD to .env, preserving other existing entries."""
    lines: list[str] = []
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
    new_lines = [line for line in lines if not line.startswith("NEO4J_PASSWORD=")]
    new_lines.append(f"NEO4J_PASSWORD={password}\n")
    with open(env_file, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
