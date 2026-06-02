"""Install command helper and MCP registration utilities."""

from __future__ import annotations

import json
import os
from pathlib import Path

from rich.prompt import Prompt

from codegraph.cli.commands._shared import _initialize_db, console


def _gemini_settings_paths() -> list[Path]:
    """Return candidate paths for Gemini CLI settings.json."""
    return [Path.home() / ".gemini" / "settings.json"]


def _gemini_settings_has_codegraph(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return "codegraph" in data.get("mcpServers", {})
    except Exception:
        return False


def _find_mcp_registrations(config_path: Path) -> list[str]:
    """Return list of config file paths where codegraph MCP server is registered."""
    found: list[str] = []

    # Project-level .mcp.json (Claude Code)
    project_mcp = config_path.parent / ".mcp.json"
    if _mcp_json_has_codegraph(project_mcp):
        found.append(str(project_mcp))

    # Project-level .gemini/settings.json (Gemini CLI)
    project_gemini = config_path.parent / ".gemini" / "settings.json"
    if _gemini_settings_has_codegraph(project_gemini):
        found.append(str(project_gemini))

    # Claude Desktop global config
    for candidate in _claude_desktop_config_paths():
        if _claude_json_has_codegraph(candidate):
            found.append(str(candidate))

    # Gemini CLI global config
    for candidate in _gemini_settings_paths():
        if _gemini_settings_has_codegraph(candidate):
            found.append(str(candidate))

    return found


def _mcp_json_has_codegraph(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return "codegraph" in data.get("mcpServers", {})
    except Exception:
        return False


def _claude_json_has_codegraph(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return "codegraph" in data.get("mcpServers", {})
    except Exception:
        return False


def _claude_desktop_config_paths() -> list[Path]:
    """Return candidate paths for Claude Desktop's claude.json on all platforms."""
    import platform

    system = platform.system()
    if system == "Darwin":
        return [
            Path.home() / "Library" / "Application Support" / "Claude" / "claude.json"
        ]
    if system == "Windows":
        appdata = Path(
            os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        )
        return [appdata / "Claude" / "claude.json"]
    # Linux
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return [xdg / "Claude" / "claude.json"]


def install_helper(config_path: Path) -> None:
    """Write MCP server registration for Claude Code, Claude Desktop, or Gemini CLI."""
    import shutil

    console.print("\n[bold cyan]CodeGraph MCP Install Wizard[/bold cyan]\n")

    if not config_path.exists():
        console.print(
            "[red]-[/red] config.yaml not found. Run [bold]codegraph init[/bold] first."
        )
        return

    # Resolve codegraph executable path
    codegraph_exe = shutil.which("codegraph") or "codegraph"

    console.print("Which AI assistant do you want to configure?\n")
    console.print("  [bold]1[/bold]  Claude Code  (project-level .mcp.json)")
    console.print("  [bold]2[/bold]  Claude Desktop  (global ~/.../claude.json)")
    console.print("  [bold]3[/bold]  Gemini CLI  (project-level .gemini/settings.json)")
    console.print("  [bold]4[/bold]  Gemini CLI  (global ~/.gemini/settings.json)")
    console.print("  [bold]5[/bold]  All\n")

    choice = Prompt.ask("Choice", choices=["1", "2", "3", "4", "5"], default="1")

    server_entry = {
        "command": codegraph_exe,
        "args": ["serve", "--config", str(config_path.resolve())],
        "env": {},
    }

    if choice in ("1", "5"):
        _write_project_mcp_json(config_path.parent / ".mcp.json", server_entry)

    if choice in ("2", "5"):
        desktop_path = _claude_desktop_config_paths()[0]
        _write_claude_desktop_json(desktop_path, server_entry)

    if choice in ("3", "5"):
        gemini_project_path = config_path.parent / ".gemini" / "settings.json"
        _write_gemini_settings_json(gemini_project_path, server_entry)

    if choice in ("4", "5"):
        gemini_global_path = _gemini_settings_paths()[0]
        _write_gemini_settings_json(gemini_global_path, server_entry)

    # Verify reachability
    console.print("\n[bold]Verifying server can start...[/bold]")
    try:
        db_manager = _initialize_db(config_path)
        if db_manager.is_connected():
            console.print(
                "   [green]+[/green] Neo4j reachable — server should start correctly"
            )
        else:
            console.print(
                "   [yellow]![/yellow] Neo4j not reachable — server will fail at startup"
            )
            console.print("      Start Neo4j first, then reload your AI assistant.")
    except Exception as e:
        console.print(f"   [yellow]![/yellow] Could not verify: {e}")

    console.print(
        "\n[bold green]Done.[/bold green] Restart your AI assistant to pick up the changes.\n"
    )


def _write_project_mcp_json(mcp_path: Path, server_entry: dict) -> None:
    """Write or update .mcp.json in the project directory."""
    data: dict = {}
    if mcp_path.exists():
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data.setdefault("mcpServers", {})["codegraph"] = server_entry
    mcp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    console.print(f"   [green]+[/green] Written to {mcp_path}")
    console.print("      Reload Claude Code (or open a new session) to activate.\n")


def _write_claude_desktop_json(desktop_path: Path, server_entry: dict) -> None:
    """Write or update Claude Desktop's claude.json."""
    desktop_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if desktop_path.exists():
        try:
            data = json.loads(desktop_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data.setdefault("mcpServers", {})["codegraph"] = server_entry
    desktop_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    console.print(f"   [green]+[/green] Written to {desktop_path}")
    console.print("      Restart Claude Desktop to activate.\n")


def _write_gemini_settings_json(path: Path, server_entry: dict) -> None:
    """Write or update Gemini CLI's settings.json."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data.setdefault("mcpServers", {})["codegraph"] = server_entry
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    console.print(f"   [green]+[/green] Written to {path}")
    console.print("      Reload Gemini CLI (or start a new session) to activate.\n")
