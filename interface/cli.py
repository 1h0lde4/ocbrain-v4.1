"""
interface/cli.py — Terminal interface. Headless, pipe-friendly, scriptable.
Usage:
  ocbrain "your query"
  ocbrain --status
  ocbrain --train coding
  ocbrain --new-module
  ocbrain --update
  ocbrain --rollback
  echo "query" | ocbrain
"""
import asyncio
import sys

import click
import httpx
from rich.console import Console
from rich.table import Table

console = Console()
BASE    = "http://localhost:7437"


def _get(path: str) -> dict:
    resp = httpx.get(f"{BASE}{path}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, data: dict = None) -> dict:
    resp = httpx.post(f"{BASE}{path}", json=data or {}, timeout=120)
    resp.raise_for_status()
    return resp.json()


@click.group(invoke_without_command=True)
@click.pass_context
@click.argument("query", required=False)
@click.option("--module", "-m", default=None, help="Force a specific module")
def cli(ctx, query, module):
    """OCBrain — local AI assistant."""
    if ctx.invoked_subcommand:
        return

    # Support pipe: echo "query" | ocbrain
    if not query and not sys.stdin.isatty():
        query = sys.stdin.read().strip()

    if query:
        try:
            result = _post("/query", {"query": query, "module": module})
            console.print(result.get("answer", "No answer returned."))
        except httpx.ConnectError:
            console.print("[red]OCBrain is not running. Start it with: ocbrain-start[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@cli.command()
def status():
    """Show module health and maturity status."""
    try:
        data = _get("/status")
        table = Table(title="OCBrain Module Status")
        table.add_column("Module",  style="cyan")
        table.add_column("Stage",   style="magenta")
        table.add_column("Score",   style="green")
        table.add_column("Queries", style="yellow")
        table.add_column("KB Chunks")
        for name, info in data.get("modules", {}).items():
            table.add_row(
                name,
                info.get("stage", "?"),
                f"{info.get('maturity_score', 0):.2f}",
                str(info.get("query_count", 0)),
                str(info.get("kb_chunks", 0)),
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]{e}[/red]")


@cli.command()
@click.argument("module_name")
def train(module_name):
    """Manually trigger a training run for a module."""
    console.print(f"[yellow]Triggering training for '{module_name}'...[/yellow]")
    try:
        result = _post(f"/train/{module_name}")
        console.print(result.get("result", "Done."))
    except Exception as e:
        console.print(f"[red]{e}[/red]")


@cli.command(name="new-module")
def new_module():
    """Interactive wizard to create a new expert module."""
    console.print("[bold cyan]New Expert Module Creator[/bold cyan]")
    name     = click.prompt("Module name (e.g. finance)")
    desc     = click.prompt("Description")
    model    = click.prompt("Bootstrap model", default="mistral")
    kw_str   = click.prompt("Keywords (comma-separated)")
    src_str  = click.prompt("Source URLs (comma-separated, or press Enter to skip)", default="")
    keywords = [k.strip() for k in kw_str.split(",") if k.strip()]
    sources  = [s.strip() for s in src_str.split(",") if s.strip()]
    try:
        result = _post("/modules/new", {
            "name": name, "desc": desc, "model": model,
            "keywords": keywords, "sources": sources,
        })
        console.print(f"[green]Module '{name}' created successfully.[/green]")
    except Exception as e:
        console.print(f"[red]{e}[/red]")


@cli.command()
def update():
    """Check for and install available updates."""
    try:
        info = _get("/updates")

        if info.get("check_failed"):
            console.print(f"[yellow]Could not check for updates: {info.get('check_error')}[/yellow]")
            return

        current = info.get("current", "?")
        if info.get("available"):
            latest = info.get("version", "?")
            console.print(f"[green]Update available: v{current} → v{latest}[/green]")
            if info.get("changelog"):
                console.print(f"[dim]{info['changelog']}[/dim]")
            if click.confirm("Install now?"):
                console.print("[yellow]Installing... this runs git pull + pip install.[/yellow]")
                result = _post("/update/install")
                console.print(f"[green]{result.get('message', 'Done.')}[/green]")
                if result.get("status") == "installing":
                    console.print("[yellow]Restart OCBrain when update completes:[/yellow]")
                    console.print("  Ctrl+C → python main.py")
        else:
            console.print(f"[green]OCBrain v{current} is up to date.[/green]")

    except httpx.ConnectError:
        console.print("[red]OCBrain is not running. Start it with: source .venv/bin/activate && python main.py[/red]")
    except Exception as e:
        console.print(f"[red]{e}[/red]")


@cli.command()
def rollback():
    """Roll back to the previous version."""
    if click.confirm("Roll back to the commit before the last update?"):
        try:
            result = _post("/rollback")
            if result.get("status") == "ok":
                console.print(f"[green]{result.get('message')}[/green]")
                console.print("[yellow]Restart OCBrain:[/yellow]  Ctrl+C → python main.py")
            else:
                console.print(f"[red]Rollback failed: {result.get('message')}[/red]")
        except Exception as e:
            console.print(f"[red]{e}[/red]")


if __name__ == "__main__":
    cli()
