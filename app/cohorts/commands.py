import click

from app.cohorts.legacy_import import import_legacy_data


@click.command("import-legacy-data")
@click.option(
    "--input",
    "input_dir",
    required=True,
    help="Path to the Daily_Refresh 'input' folder (containing ramp/, manual/, kairon/ subfolders).",
)
@click.option(
    "--year",
    type=int,
    default=None,
    help="Calendar year the ramp workbook's month-day text implies (defaults to the current year).",
)
def import_legacy_data_command(input_dir, year):
    """One-time backfill from the legacy Daily_Refresh spreadsheet pipeline (Phase 2)."""
    import_legacy_data(input_dir, year=year, log=click.echo)
    click.echo("Import complete.")
