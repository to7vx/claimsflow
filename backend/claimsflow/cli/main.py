"""Click CLI for ClaimsFlow.

Subcommands:
- init     — create DB tables (Module 2)
- seed     — populate synthetic data (Module 2)
- process  — adjudicate a claim JSON file or a directory of them (Module 6)
- status   — print current status + decision for a claim ID (Module 6)
- stats    — row counts per table (Module 2)
- serve    — start the FastAPI app via uvicorn (Module 6)
- demo     — scripted end-to-end demo (Module 6)
- hello    — smoke test (Module 1)
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Force UTF-8 on Windows consoles so Rich can emit ✓ / ✗ / Arabic glyphs.
# CP1252 (the legacy default) can't encode them and crashes the CLI.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

import click
from rich.console import Console
from rich.json import JSON as RichJSON
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from sqlalchemy import select

from claimsflow import __version__
from claimsflow.core.config import get_settings
from claimsflow.core.db import Base, get_engine, get_session_factory
from claimsflow.core.logging import configure_logging
from claimsflow.models import (
    AuditLog,
    Claim,
    ClaimStatus,
    ClaimSubmission,
    Decision,
)
from claimsflow.pipeline import process_claim
from claimsflow.seed import seed_database

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="claimsflow")
def cli() -> None:
    """ClaimsFlow — auto-adjudicate medical claims from the command line."""
    configure_logging()


# ─────────────── hello / init / seed / stats ───────────────


@cli.command()
def hello() -> None:
    """Smoke-test command — prints a banner to confirm the CLI is wired up."""
    click.echo(f"ClaimsFlow v{__version__} — scaffold OK")


@cli.command()
@click.option("--reset", is_flag=True, help="Drop all tables first (destroys data).")
def init(reset: bool) -> None:
    """Initialize the database — create all tables."""
    settings = get_settings()
    engine = get_engine()
    if reset:
        console.print("[yellow]Dropping existing tables…[/yellow]")
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    console.print(f"[green]✓[/green] Database ready at [cyan]{settings.database_url}[/cyan]")


@cli.command()
@click.option("--small", "mode", flag_value="small", default=True, help="Smaller dataset (default).")
@click.option("--full", "mode", flag_value="full", help="Full dataset per spec.")
@click.option("--seed", "random_seed", default=42, type=int, help="Deterministic random seed.")
def seed(mode: str, random_seed: int) -> None:
    """Populate the database with synthetic Saudi-healthcare data."""
    session = get_session_factory()()
    try:
        with console.status(f"[bold green]Generating {mode} dataset…"):
            counts = seed_database(session, mode=mode, random_seed=random_seed)
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    table = Table(title="Seed complete", header_style="bold magenta")
    table.add_column("Entity", style="cyan")
    table.add_column("Count", justify="right", style="green")
    for entity, n in counts.items():
        table.add_row(entity, str(n))
    console.print(table)


@cli.command()
def stats() -> None:
    """Quick row counts per table."""
    from sqlalchemy import func

    from claimsflow.models import Member, Plan, Provider

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


# ─────────────── process ───────────────


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def process(path: Path) -> None:
    """Adjudicate a single claim JSON file or a directory of them.

    The JSON must match the ClaimSubmission schema (same as POST /claims/submit).
    """
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    if not files:
        console.print(f"[yellow]No .json files found at {path}[/yellow]")
        return

    console.print(f"[bold]Processing {len(files)} claim file(s)[/bold]")
    asyncio.run(_run_batch(files))


async def _run_batch(files: list[Path]) -> None:
    session = get_session_factory()()
    results: list[tuple[str, str, str]] = []
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Adjudicating…", total=len(files))
            for file in files:
                payload = ClaimSubmission.model_validate_json(file.read_text())
                claim = _build_claim_from_submission(payload)
                session.add(claim)
                session.flush()
                decision = await process_claim(session, claim.claim_id)
                session.commit()
                results.append((file.name, claim.claim_id, decision.decision_type))
                progress.advance(task)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    table = Table(title="Batch processing complete", header_style="bold magenta")
    table.add_column("File", style="cyan")
    table.add_column("Claim ID", style="white")
    table.add_column("Decision", style="green")
    for fname, cid, dtype in results:
        table.add_row(fname, cid, dtype)
    console.print(table)


def _build_claim_from_submission(payload: ClaimSubmission) -> Claim:
    import uuid

    claim_id = f"CLM-{uuid.uuid4().hex[:10].upper()}"
    total = sum(li.quantity * li.unit_cost for li in payload.line_items)
    return Claim(
        claim_id=claim_id,
        claim_type=payload.claim_type.value,
        member_id=payload.member_id,
        provider_id=payload.provider_id,
        service_date=payload.service_date,
        submission_date=datetime.utcnow(),
        diagnosis_codes=payload.diagnosis_codes,
        procedure_codes=payload.procedure_codes,
        line_items=[li.model_dump() for li in payload.line_items],
        clinical_notes=payload.clinical_notes,
        total_billed=total,
        status=ClaimStatus.RECEIVED.value,
    )


# ─────────────── status ───────────────


@cli.command()
@click.argument("claim_id")
def status(claim_id: str) -> None:
    """Print the current status, decision, and recent audit trail for a claim."""
    session = get_session_factory()()
    try:
        claim = session.get(Claim, claim_id)
        if claim is None:
            console.print(f"[red]Claim {claim_id} not found[/red]")
            return
        decision = session.scalars(
            select(Decision).where(Decision.claim_id == claim_id)
        ).one_or_none()
        logs = session.scalars(
            select(AuditLog)
            .where(AuditLog.claim_id == claim_id)
            .order_by(AuditLog.timestamp)
        ).all()
    finally:
        session.close()

    summary = (
        f"[bold]{claim.claim_id}[/bold]  status=[cyan]{claim.status}[/cyan]  "
        f"billed=[green]{claim.total_billed:.2f} SAR[/green]\n"
        f"member={claim.member_id}  provider={claim.provider_id}  "
        f"service_date={claim.service_date}"
    )
    console.print(Panel(summary, title="Claim", border_style="blue"))

    if decision:
        console.print(
            Panel(
                decision.reasoning or "(no reasoning)",
                title=f"Decision — {decision.decision_type}  (confidence {decision.confidence_score:.2f})",
                border_style="green",
            )
        )
        if decision.flags:
            console.print(f"[yellow]Flags:[/yellow] {', '.join(decision.flags)}")

    if logs:
        table = Table(title="Audit trail", header_style="bold magenta")
        table.add_column("Time", style="cyan")
        table.add_column("Event")
        table.add_column("Data", style="white")
        for log in logs[-10:]:
            table.add_row(
                log.timestamp.isoformat(timespec="seconds"),
                log.event_type,
                json.dumps(log.event_data, ensure_ascii=False)[:80],
            )
        console.print(table)


# ─────────────── serve ───────────────


@cli.command()
@click.option("--host", default=None, help="Override API_HOST.")
@click.option("--port", default=None, type=int, help="Override API_PORT.")
@click.option("--reload", is_flag=True, help="Enable autoreload (dev only).")
def serve(host: str | None, port: int | None, reload: bool) -> None:
    """Start the FastAPI server via uvicorn."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "claimsflow.api.app:app",
        host=host or settings.api_host,
        port=port or settings.api_port,
        reload=reload,
    )


# ─────────────── demo ───────────────


@cli.command()
@click.option("--count", default=20, type=int, help="Number of pre-seeded claims to adjudicate.")
def demo(count: int) -> None:
    """Run a scripted demo: pick N seeded RECEIVED claims, process them, print summary."""
    session = get_session_factory()()
    try:
        pending = session.scalars(
            select(Claim).where(Claim.status == ClaimStatus.RECEIVED.value).limit(count)
        ).all()
        if not pending:
            console.print("[yellow]No RECEIVED claims found. Run `claimsflow seed` first.[/yellow]")
            return

        asyncio.run(_run_demo(session, pending))

        # Summary
        from collections import Counter

        decisions = session.scalars(
            select(Decision.decision_type)
        ).all()
        breakdown = Counter(decisions)
        table = Table(title=f"Demo — adjudicated {len(pending)} claims", header_style="bold magenta")
        table.add_column("Decision")
        table.add_column("Count", justify="right", style="green")
        for dtype, n in breakdown.most_common():
            table.add_row(dtype, str(n))
        console.print(table)
    finally:
        session.close()


async def _run_demo(session, claims: list[Claim]) -> None:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Adjudicating seeded claims…", total=len(claims))
        for claim in claims:
            await process_claim(session, claim.claim_id)
            session.commit()
            progress.advance(task)


if __name__ == "__main__":
    cli()
