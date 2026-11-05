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
import sys

import click
import httpx
from rich.console import Console
from rich.table import Table

console = Console()
BASE    = "http://localhost:7437"


class SubcommandFirstGroup(click.Group):
    """
    click.Group variant whose registered subcommands take priority over the
    group's free-form [QUERY] positional argument.

    Stock click parsing consumes the first non-option token of
    `ocbrain status` into the group's QUERY argument, leaving
    ctx._protected_args empty — every subcommand becomes unreachable (and an
    unknown option such as memory-doctor's --db aborts at the group level).
    With this class the first positional token is checked against the
    registered command table; when it names a command, parsing continues with
    the group's positional arguments hidden, so the token falls through to
    the subcommand path exactly as if no [QUERY] argument existed. A free
    text query (`ocbrain "why is it slow"`) contains no registered command
    name and is parsed as before.
    """

    def parse_args(self, ctx, args):
        if (args and not args[0].startswith("-")
                and args[0] in self.commands):
            positional_params = [p for p in self.params
                                 if isinstance(p, click.Argument)]
            if positional_params:
                self.params = [p for p in self.params
                               if not isinstance(p, click.Argument)]
                try:
                    result = super().parse_args(ctx, args)
                    # The group callback still runs (invoke_without_command
                    # groups invoke it before the subcommand); it expects the
                    # positional to exist. With the subcommand claiming the
                    # free-form token, the query path is simply unused.
                    ctx.params.setdefault("query", None)
                    return result
                finally:
                    self.params = positional_params
        return super().parse_args(ctx, args)


def _get(path: str) -> dict:
    resp = httpx.get(f"{BASE}{path}", timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, data: dict = None) -> dict:
    resp = httpx.post(f"{BASE}{path}", json=data or {}, headers={"X-OCBrain-Local": "1"}, timeout=120)
    resp.raise_for_status()
    return resp.json()


@click.group(invoke_without_command=True, cls=SubcommandFirstGroup)
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
        _post("/modules/new", {
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


# ── Rev 3 (G4-FTS remediation): local memory maintenance commands ────────────
#
# These commands run LOCALLY on the machine holding the database files and
# deliberately do NOT go through the daemon HTTP API: migration and full
# verification must happen while every OCBrain process is STOPPED and drained
# (deployment contract, Amendment 2 §C). A live process would hold WAL state
# and could revive a WAL after the maintenance runner's final checkpoint.
#
# Default database path follows the configured memory database:
#   settings.toml → [memory] database   (fallback: .data/memory/unified.db)


def _memory_db_path(db: str | None) -> str:
    if db:
        return db
    try:
        from core.config import config
        return str(config.get("memory.database") or ".data/memory/unified.db")
    except Exception:
        return ".data/memory/unified.db"


def _open_verify_connection(db_path: str):
    """
    Open a connection for verification.

    The FTS5 `integrity-check(rank=1)` command is a read operation on the
    database image but is implemented as an INSERT on the FTS virtual table,
    so SQLite treats it as a WRITE and refuses it on read-only connections
    ("attempt to write a readonly database"). Verification therefore needs a
    read-write connection; every executed statement is non-mutating by
    contract. `memory-doctor` (which skips the rank=1 check) still prefers a
    genuinely read-only connection.
    """
    import sqlite3
    try:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True,
                               timeout=20.0)
    except sqlite3.Error:
        pass
    return sqlite3.connect(db_path, timeout=20.0)


def _print_migration_report(report) -> None:
    """Render a MaintenanceReport (from core.memory.sqlite_migration)."""
    console.print(f"  database: [cyan]{report.db_path}[/cyan]")
    est = report.space_estimate or {}
    console.print(
        f"  space estimate (estimate, not a guarantee): "
        f"~{est.get('estimate_extra_bytes', '?')} bytes extra; "
        f"free: {est.get('free_bytes', '?')} bytes")
    table = Table(title="Migration steps")
    table.add_column("Step", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Detail")
    for step in report.steps:
        table.add_row(step.get("step", "?"), step.get("status", "?"),
                      step.get("detail", ""))
    console.print(table)

    ver = report.verification or {}
    if ver.get("passed") is not None:
        console.print(
            f"  verification: passed={ver.get('passed')} "
            f"total_cost_s={ver.get('total_cost_s')}")
        for finding in ver.get("findings", []):
            status = finding.get("status", "?")
            style = "[green]" if status in ("pass", "not_applicable") else "[red]"
            console.print(
                f"    {style}[{status}][/] {finding.get('scope')} / "
                f"{finding.get('name')}: {finding.get('detail')}")
    if report.ledger_row:
        console.print(f"  ledger row recorded: {report.ledger_row}")
    if report.checkpoint:
        console.print(f"  post-commit checkpoint: {report.checkpoint}")
    console.print(
        f"  WAL bytes before/after: "
        f"{report.wal_bytes_before} -> {report.wal_bytes_after}")
    if report.failure:
        console.print(f"  [red]failure:[/] {report.failure}")
    if report.remediation:
        console.print(f"  [yellow]remediation:[/] {report.remediation}")
    if report.preserved_files:
        console.print(
            f"  [red]corrupt database preserved (not rebuilt); copies:[/red] "
            f"{report.preserved_files}")


_MIGRATION_DEPLOYMENT_CONTRACT = (
    "Deployment contract (Amendment 2 §C): migration runs ONLY with all\n"
    " OCBrain processes stopped and drained on this machine. Live mutations\n"
    " during migration invalidate its locks; the final WAL checkpoint would\n"
    " be silently undone by a concurrently opened connection.")


@cli.command(name="memory-migrate")
@click.option("--db", "db", default=None,
              help="Database file to migrate (default: configured "
                   "[memory] database, e.g. .data/memory/unified.db)")
@click.option("--skip-checkpoint", is_flag=True, default=False,
              help="Do not run the post-commit WAL checkpoint")
def memory_migrate(db, skip_checkpoint):
    """Run the deferred memory migration while the app is STOPPED.

    Migrates one SQLite memory database to the Rev 3 canonical contract
    (canonical triggers, FTS external-content rebuild, indexes, ledger row,
    verification). Concurrent invocations are serialized by SQLite and an
    advisory lock file; a second runner re-reads state after locking and
    reports 'already_applied' when the first one has finished.
    """
    console.print("[bold yellow]" + _MIGRATION_DEPLOYMENT_CONTRACT +
                  "[/bold yellow]")
    db_path = _memory_db_path(db)
    console.print(f"[cyan]Migrating {db_path} …[/cyan]")
    try:
        from core.memory.sqlite_migration import run_maintenance_migration
        report = run_maintenance_migration(
            db_path, run_final_checkpoint=not skip_checkpoint)
    except Exception as e:
        console.print(f"[red]migration abort: {e}[/red]")
        raise SystemExit(1)

    console.print(f"[bold]outcome:[/bold] {report.outcome}")
    _print_migration_report(report)
    if report.outcome == "migrated":
        console.print("[green]Migration committed and verified. "
                      "Start OCBrain normally.[/green]")
    elif report.outcome == "already_applied":
        console.print("[yellow]No work: migration already applied "
                      "(re-read after lock).[/yellow]")
    elif report.outcome == "preserved_corrupt":
        console.print("[red]Database corruption detected — the database was "
                      "NOT modified or rebuilt. Invoke memory recovery "
                      "procedures.[/red]")
        raise SystemExit(1)
    else:
        raise SystemExit(1)


@cli.command(name="memory-doctor")
@click.option("--db", "db", default=None,
              help="Database file to inspect (default: configured "
                   "[memory] database)")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Emit the full inventory as JSON")
def memory_doctor(db, as_json):
    """Read-only diagnosis: SQLite runtime gate + checkpoint inventory +
    migration state. Writes nothing to the database (no wal revival beyond
    opening it read-only)."""
    import json as _json
    import sqlite3
    from core.memory.sqlite_migration import (
        collect_checkpoint_inventory,
        inspect_migration_state,
    )
    from core.memory.sqlite_integrity import validate_readiness
    from core.memory.sqlite_runtime import (
        classify_wal_safety,
        collect_runtime_inventory,
        resolve_gate_mode,
    )
    from core.memory.sqlite_contract import MemoryReadinessError

    db_path = _memory_db_path(db)
    inventory: dict = {"database": db_path}

    # 1. Runtime compatibility inventory + verdict (Amendment 1)
    runtime_inv = collect_runtime_inventory()
    decision = classify_wal_safety(runtime_inv)
    inventory["runtime"] = runtime_inv
    inventory["runtime_decision"] = {
        "decision": decision.decision,
        "wal_safe": decision.wal_safe,
        "affected_by_wal_reset_bug": decision.affected_by_wal_reset_bug,
        "full_wal_support": decision.full_wal_support,
        "reason": decision.reason,
        "remediation": decision.remediation,
    }
    inventory["gate_mode"] = resolve_gate_mode()

    if not as_json:
        console.print("[bold]SQLite runtime gate[/bold] "
                      f"(mode={inventory['gate_mode']})")
        console.print(f"  python: {runtime_inv['python_version']}")
        console.print(f"  sqlite3.sqlite_version: "
                      f"{runtime_inv['sqlite3_sqlite_version']}")
        console.print(f"  SELECT sqlite_version(): "
                      f"{runtime_inv['sqlite_version_sql']}")
        console.print(f"  sqlite_source_id: {runtime_inv['sqlite_source_id']}")
        console.print(f"  platform: {runtime_inv['os']}")
        console.print(f"  verdict: {decision.decision} "
                      f"(wal_safe={decision.wal_safe}, "
                      f"full_wal_support={decision.full_wal_support})")
        console.print(f"  reason: {decision.reason}")
        if decision.remediation:
            console.print(f"  remediation: {decision.remediation}")

    # 2. Checkpoint inventory (Amendment 10) — read-only connection
    inventory["checkpoint_inventory"] = collect_checkpoint_inventory(db_path)

    # 3. Migration state + readiness (inspection only, never enforcement)
    try:
        conn = _open_verify_connection(db_path)
        try:
            state = inspect_migration_state(conn)
            inventory["migration_state"] = {
                "schema_state": state.state,
                "detail": state.finding,
                "remediation": state.remediation,
            }
            inventory["readiness"] = validate_readiness(conn)
        finally:
            conn.close()
    except sqlite3.Error as e:
        inventory["migration_state"] = {"schema_state": "unreadable",
                                        "detail": str(e)}
    except MemoryReadinessError as e:
        inventory["migration_state"] = {"schema_state": "refused",
                                        "detail": str(e)}

    if not as_json:
        ci = inventory["checkpoint_inventory"]
        console.print("[bold]Checkpoint inventory[/bold]")
        console.print(f"  wal_bytes: {ci.get('wal_bytes')}")
        console.print(f"  automatic checkpointing: "
                      f"{ci.get('automatic_checkpointing')}")
        ms = inventory.get("migration_state", {})
        console.print(f"[bold]Migration state:[/] {ms}")
        rd = inventory.get("readiness")
        if rd:
            console.print("[bold]Readiness (inspection only; this command "
                          "does not gate the app):[/bold]")
            console.print(f"  passed={rd.get('passed')} "
                          f"cost_s={rd.get('total_cost_s')}")
            for finding in rd.get("checks", []):
                status = finding.get("status")
                style = "[green]" if status in ("pass", "not_applicable") \
                    else "[red]"
                console.print(
                    f"    {style}[{status}][/] {finding.get('name')}: "
                    f"{finding.get('detail')}")
    else:
        console.print(_json.dumps(inventory, indent=2, default=str))


@cli.command(name="memory-verify")
@click.option("--db", "db", default=None,
              help="Database file to verify (default: configured "
                   "[memory] database)")
def memory_verify(db):
    """Run the FULL memory integrity validation now (Amendment 3 §C).

    Explicitly runs every check that normal startup intentionally skips:
    whole-database integrity_check, foreign_key_check (when applicable),
    FTS5 rank=1 integrity-check, real MATCH retrieval probes, plus the
    content-row identity and FTS configuration audits. No content is
    modified (the FTS5 integrity-check needs a writable connection but never
    alters the image); the measured validation cost is reported.
    """
    import sqlite3
    import time
    from core.memory.sqlite_contract import FTS_TABLE
    from core.memory.sqlite_integrity import (
        audit_trigger_contract,
        read_fts_configuration,
        read_secure_delete_policy,
        run_full_integrity_validation,
        verify_content_row_identity,
    )

    db_path = _memory_db_path(db)
    console.print(f"[cyan]Verifying {db_path} …[/cyan]")

    try:
        conn = sqlite3.connect(db_path, timeout=20.0)
    except sqlite3.Error as e:
        console.print(f"[red]cannot open {db_path}: {e}[/red]")
        raise SystemExit(1)

    t0 = time.time()
    try:
        result = run_full_integrity_validation(conn)
        identity = verify_content_row_identity(conn)
        config = read_fts_configuration(conn)
        trig = audit_trigger_contract(conn)
        secure = read_secure_delete_policy(conn)
    finally:
        try:
            conn.close()
        except sqlite3.Error:
            pass

    wall_cost = time.time() - t0

    table = Table(title="Memory integrity findings")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("s", style="dim")
    table.add_column("Detail")
    for finding in result["findings"]:
        status = finding.get("status", "?")
        style = "[green]" if status in ("pass", "not_applicable") else "[red]"
        table.add_row(f"{finding.get('scope')}/{finding.get('name')}",
                      f"{style}{status}[/]",
                      f"{finding.get('duration_s', 0):.4f}",
                      finding.get("detail", ""))
    console.print(table)

    console.print(f"  validation passed: "
                  f"{'[green]YES[/]' if result['passed'] else '[red]NO[/]'}")
    console.print(f"  checks total_cost_s: {result['total_cost_s']} "
                  f"(wall {wall_cost:.4f}s incl. open/close)")
    console.print(f"  content-row identity: "
                  f"{'[green]PASSED[/]' if identity.get('passed') else '[red]FAILED[/]'}"
                  f" — identity is the FTS "
                  f"{identity.get('content_rowid', 'rowid')} column "
                  f"(hidden rowid persistence remains an OPEN risk: VACUUM "
                  f"may renumber rows without an explicit alias)")
    if not identity.get("passed"):
        for finding in identity.get("checks", []):
            console.print(f"    [red]{finding.status}[/] "
                          f"{finding.name}: {finding.detail}")
    console.print(f"  FTS configuration: {config.get('classification')} "
                  f"({config.get('reason', '')})")
    console.print(f"  trigger contract: {trig.get('classification')} "
                  f"({trig.get('reason', '')})")
    console.print(f"  FTS table: [cyan]{FTS_TABLE}[/cyan]; "
                  f"secure-delete policy: {secure.get('fts5_secure_delete')} "
                  f"(FTS5) / {secure.get('core_pragma_secure_delete')} "
                  f"(SQLite core PRAGMA)")

    if not result["passed"] or not identity.get("passed"):
        raise SystemExit(1)
    console.print("[green]Verification complete: all independent checks "
                  "passed.[/green]")


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
