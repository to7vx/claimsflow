"""CLI entry point. Subcommands are added in Module 6."""

from __future__ import annotations

import click

from claimsflow import __version__


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="claimsflow")
def cli() -> None:
    """ClaimsFlow — auto-adjudicate medical claims from the command line."""


@cli.command()
def hello() -> None:
    """Smoke-test command — prints a banner to confirm the CLI is wired up."""
    click.echo(f"ClaimsFlow v{__version__} — scaffold OK")


if __name__ == "__main__":
    cli()
