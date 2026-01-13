"""Output formatters for query results.

This module provides different output formats for Arrow Tables:
- table: Rich-formatted table (default, for terminal display)
- json: JSON array of records
- csv: CSV format with header
- arrow: Arrow schema and metadata display
"""

from enum import Enum
from io import StringIO

import pyarrow as pa
from rich.console import Console
from rich.table import Table


class OutputFormat(str, Enum):
    """Supported output formats for query results."""

    TABLE = "table"
    JSON = "json"
    CSV = "csv"
    ARROW = "arrow"


def format_as_table(table: pa.Table, console: Console) -> None:
    """Format Arrow Table as Rich table and print to console.

    Args:
        table: PyArrow Table to format.
        console: Rich Console to print to.
    """
    rich_table = Table(title="Query Results")

    # Add columns
    for name in table.column_names:
        rich_table.add_column(name, style="cyan")

    # Add rows
    for i in range(table.num_rows):
        row = [str(table.column(name)[i].as_py()) for name in table.column_names]
        rich_table.add_row(*row)

    console.print(rich_table)
    console.print(f"[dim]{table.num_rows} row(s)[/dim]")


def format_as_json(table: pa.Table) -> str:
    """Format Arrow Table as JSON array of records.

    Args:
        table: PyArrow Table to format.

    Returns:
        JSON string representation.
    """
    import json

    # Convert to list of dicts
    records = table.to_pylist()
    return json.dumps(records, indent=2, default=str)


def format_as_csv(table: pa.Table) -> str:
    """Format Arrow Table as CSV with header.

    Args:
        table: PyArrow Table to format.

    Returns:
        CSV string representation.
    """
    import csv

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(table.column_names)

    # Write rows
    for i in range(table.num_rows):
        row = [table.column(name)[i].as_py() for name in table.column_names]
        writer.writerow(row)

    return output.getvalue()


def format_as_arrow_schema(table: pa.Table, console: Console) -> None:
    """Format Arrow Table schema and metadata for display.

    Since Arrow binary format can't be printed to terminal, this displays
    the schema information which is valuable for learning about Arrow types.

    Args:
        table: PyArrow Table to format.
        console: Rich Console to print to.
    """
    console.print("[bold]Arrow Schema[/bold]")
    console.print()

    schema_table = Table(title="Fields")
    schema_table.add_column("Name", style="cyan")
    schema_table.add_column("Type", style="green")
    schema_table.add_column("Nullable", style="yellow")

    for field in table.schema:
        schema_table.add_row(field.name, str(field.type), str(field.nullable))

    console.print(schema_table)
    console.print()
    console.print(f"[dim]Rows: {table.num_rows}[/dim]")
    console.print(f"[dim]Columns: {table.num_columns}[/dim]")

    # Show memory usage if available
    nbytes = table.nbytes
    if nbytes > 1024 * 1024:
        size_str = f"{nbytes / (1024 * 1024):.2f} MB"
    elif nbytes > 1024:
        size_str = f"{nbytes / 1024:.2f} KB"
    else:
        size_str = f"{nbytes} bytes"
    console.print(f"[dim]Memory: {size_str}[/dim]")


def format_output(
    table: pa.Table,
    format: OutputFormat,
    console: Console,
) -> str | None:
    """Format Arrow Table according to specified output format.

    Args:
        table: PyArrow Table to format.
        format: Output format to use.
        console: Rich Console for table/arrow output.

    Returns:
        String output for json/csv formats, None for table/arrow (printed directly).
    """
    if format == OutputFormat.TABLE:
        format_as_table(table, console)
        return None
    elif format == OutputFormat.JSON:
        return format_as_json(table)
    elif format == OutputFormat.CSV:
        return format_as_csv(table)
    elif format == OutputFormat.ARROW:
        format_as_arrow_schema(table, console)
        return None
    else:
        raise ValueError(f"Unknown output format: {format}")
