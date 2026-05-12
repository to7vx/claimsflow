"""Click CLI entry point.

Subcommands are built up across modules:
- Module 1: `hello` (smoke test)
- Module 2: `init`, `seed`
- Module 5+: `serve`, `process`, `status`, `stats`, `demo` (added later)
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from claimsflow import __version__
from claimsflow.core.config import get_settings
from claimsflow.core.db import Base, get_engine, get_session_factory
from claimsflow.core.logging import configure_logging
from claimsflow.seed import seed_database

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="claimsflow")
def cli() -> None:
    """ClaimsFlow — auto-adjudicate medical claims from the command line."""
    configure_logging()


@cli.command()
def hello() -> None:
    """Smoke-test command — prints a banner to confirm the CLI is wired up."""
    click.echo(f"ClaimsFlow v{__version__} — scaffold OK")


@cli.command()
@click.option(
    "--reset",
    is_flag=True,
    help="Drop all tables before creating them. Destroys existing data.",
)
def init(reset: bool) -> None:
    """Initialize the database — create all tables.

    Use `--reset` to drop everything first (development only).
    """
    settings = get_settings()
    engine = get_engine()
    if reset:
        console.print("[yellow]Dropping existing tables…[/yellow]")
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    console.print(
        f"[green]✓[/green] Database initialized at [cyan]{settings.database_url}[/cyan]"
    )


@cli.command()
@click.option(
    "--small",
    "mode",
    flag_value="small",
    default=True,
    help="Smaller dataset suitable for tests / quick demos (default).",
)
@click.option(
    "--full",
    "mode",
    flag_value="full",
    help="Full dataset per spec (50 plans / 200 providers / 500 members / 1000 claims).",
)
@click.option(
    "--seed",
    "random_seed",
    default=42,
    type=int,
    help="Random seed for deterministic generation.",
)
def seed(mode: str, random_seed: int) -> None:
    """Populate the database with synthetic Saudi-healthcare data."""
    session = get_session_factory()()
    try:
        with console.status(f"[bold green]Generating {mode} dataset…[/bold green]"):
            counts = seed_database(session, mode=mode, random_seed=random_seed)
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    table = Table(title="Seed complete", show_header=True, header_style="bold magenta")
    table.add_column("Entity", style="cyan")
    table.add_column("Count", justify="right", style="green")
    for entity, n in counts.items():
        table.add_row(entity, str(n))
    console.print(table)


@cli.command()
def stats() -> None:
    """Quick row counts per table. Useful sanity-check after seeding."""
    from sqlalchemy import func, select

    from claimsflow.models import AuditLog, Claim, Decision, Member, Plan, Provider

    session = get_session_factory()()
    try:
        rows = [
            ("plans", session.scalar(select(func.count()).select_from(Plan))),
            ("providers", session.scalar(select(func.count()).select_from(Provider))),
            ("members", session.scalar(select(func.count()).select_from(Member))),
            ("claims", session.scalar(select(func.count()).select_from(Claim))),
            ("decisions", session.scalar(select(func.count()).select_from(Decision))),
            ("audit_logs", session.scalar(select(func.count()).select_from(AuditLog))),
        ]
    finally:
        session.close()

    table = Table(title="ClaimsFlow — Database stats", header_style="bold magenta")
    table.add_column("Table", style="cyan")
    table.add_column("Rows", justify="right", style="green")
    for name, count in rows:
        table.add_row(name, str(count))
    console.print(table)


if __name__ == "__main__":
    cli()
