"""CLI entry point for ralph."""

import click


@click.command()
@click.version_option(version="0.1.0")
def main() -> None:
    """Ralph: AI orchestration CLI for autonomous development workflows."""
    click.echo("Ralph CLI - Coming soon!")


if __name__ == "__main__":
    main()
