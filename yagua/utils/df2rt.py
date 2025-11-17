"""Yagua - DataFrame to Rich Table Converter.

This module provides utilities to convert pandas DataFrames into Rich Table
objects for beautiful, formatted terminal output. It handles automatic column
type detection, formatting, and styling to create professional-looking tables
in the CLI.

Functions
---------
df_to_rich_table : function
    Convert a pandas DataFrame to a Rich Table with styling.
format_value : function
    Format individual cell values (especially floats).
column_format : function
    Determine column formatting based on data type.

Features
--------
- Automatic type-based column alignment (right-align for numbers)
- Customizable float formatting
- Optional index display
- Alternating row colors for readability
- Clean SIMPLE_HEAD box style

Attribution
-----------
Based on: https://gist.github.com/neelabalan/33ab34cf65b43e305c3f12ec6db05938
Modified for yagua project with additional formatting options.

Examples
--------
Basic conversion:
>>> import pandas as pd
>>> from yagua.utils.df2rt import df_to_rich_table
>>> df = pd.DataFrame({'Name': ['Alice', 'Bob'], 'Score': [95.5, 87.3]})
>>> table = df_to_rich_table(df)
>>> console.print(table)

With custom float formatting:
>>> table = df_to_rich_table(df, float_fmt="{:.2f}")
>>> console.print(table)

Without index:
>>> table = df_to_rich_table(df, show_index=False)
>>> console.print(table)
"""

import inspect
from datetime import datetime
from typing import Optional

import numpy as np

import pandas as pd

from rich import box
from rich.console import Console
from rich.table import Table


# ============================================================================
# CONSTANTS
# ============================================================================

#: Console instance for Rich output (used in main block for demos).
console = Console()


# ============================================================================
# PUBLIC FUNCTIONS
# ============================================================================


def format_value(value, float_fmt):
    """Format a cell value, applying special formatting for floats.

    Parameters
    ----------
    value : Any
        The value to format (can be any type).
    float_fmt : str
        Format string for float values (e.g., "{:.2f}", "{:.3f}").

    Returns
    -------
    str
        Formatted string representation of the value.

    Examples
    --------
    >>> format_value(3.14159, "{:.2f}")
    '3.14'
    >>> format_value("hello", "{:.2f}")
    'hello'
    >>> format_value(42, "{:.2f}")
    '42'
    """
    if isinstance(value, float):
        return float_fmt.format(value)
    return str(value)


def column_format(type):
    """Determine column formatting options based on data type.

    This function analyzes the column's data type and returns
    formatting options for Rich Table columns. Numeric columns
    are right-aligned for better readability.

    Parameters
    ----------
    type : type or numpy.dtype
        The data type of the column. Can be a Python type or numpy dtype.

    Returns
    -------
    dict
        Dictionary of formatting options to pass to Rich Table's add_column().
        Contains 'justify': 'right' for numeric types, empty dict otherwise.

    Examples
    --------
    >>> import numpy as np
    >>> column_format(float)
    {'justify': 'right'}
    >>> column_format(np.float64)
    {'justify': 'right'}
    >>> column_format(str)
    {}
    >>> column_format(int)
    {'justify': 'right'}
    """
    # Extract type from numpy dtype if necessary
    type = type.type if isinstance(type, np.dtype) else type
    cfmt = {}
    # Right-align numeric columns
    if issubclass(type, (float, int, complex, np.number)):
        cfmt["justify"] = "right"
    return cfmt


def df_to_rich_table(
    pandas_dataframe: pd.DataFrame,
    show_index: bool = True,
    index_name: Optional[str] = None,
    header_style: str = "bold magenta",
    float_fmt: str = "{:.3f}",
) -> Table:
    """Convert a pandas DataFrame into a Rich Table object.

    This function creates a styled Rich Table from a pandas DataFrame,
    preserving the data structure and adding visual formatting for
    terminal display. The table automatically detects column types and
    applies appropriate formatting (e.g., right-alignment for numbers).

    Parameters
    ----------
    pandas_dataframe : pd.DataFrame
        A Pandas DataFrame to be converted to a Rich Table.
    show_index : bool, optional
        If True, add a column with row indices to the table.
        Defaults to True.
    index_name : str, optional
        The column name to give to the index column. If None,
        the index column will have no header (empty string).
        Defaults to None.
    header_style : str, optional
        Rich style string for table headers.
        Defaults to "bold magenta".
    float_fmt : str, optional
        Format string for float values (e.g., "{:.2f}" for 2 decimals).
        Defaults to "{:.3f}".

    Returns
    -------
    rich.table.Table
        A Rich Table instance populated with the DataFrame values,
        styled with:
        - Alternating row colors (normal and dim)
        - Type-based column alignment (right for numbers)
        - SIMPLE_HEAD box style for clean appearance

    Notes
    -----
    The function automatically:
    - Right-aligns numeric columns (int, float, complex, numpy numbers)
    - Left-aligns text columns
    - Applies custom float formatting to all float values
    - Converts all values to strings for display

    Examples
    --------
    Basic usage with index:
    >>> import pandas as pd
    >>> from yagua.utils.df2rt import df_to_rich_table
    >>> df = pd.DataFrame({
    ...     'Name': ['Alice', 'Bob', 'Charlie'],
    ...     'Score': [95.5, 87.3, 91.2]
    ... })
    >>> table = df_to_rich_table(df, show_index=True, index_name='#')
    >>> console.print(table)

    Without index and custom float format:
    >>> table = df_to_rich_table(
    ...     df,
    ...     show_index=False,
    ...     float_fmt="{:.1f}"
    ... )
    >>> console.print(table)

    Custom header style:
    >>> table = df_to_rich_table(
    ...     df,
    ...     header_style="bold cyan"
    ... )
    >>> console.print(table)
    """
    # Initialize Rich Table with header styling
    rich_table = Table(show_header=True, header_style=header_style)

    # Add index column if requested
    if show_index:
        index_name = str(index_name) if index_name else ""
        rich_table.add_column(index_name)

    # Add data columns with type-appropriate formatting
    for column in pandas_dataframe.columns:
        column_fmt = column_format(pandas_dataframe[column].dtype)
        rich_table.add_column(str(column), **column_fmt)

    # Populate table rows with formatted values
    for index, value_list in enumerate(pandas_dataframe.values.tolist()):
        row = [str(index)] if show_index else []
        row += [format_value(x, float_fmt) for x in value_list]
        rich_table.add_row(*row)

    # Apply table styling
    rich_table.row_styles = ["none", "dim"]  # Alternating row colors
    rich_table.box = box.SIMPLE_HEAD  # Clean header-only box style

    return rich_table


if __name__ == "__main__":
    # Demo script showing df_to_rich_table functionality
    # Run with: python -m yagua.utils.df2rt

    sample_data = {
        "Date": [
            datetime(year=2019, month=12, day=20),
            datetime(year=2018, month=5, day=25),
            datetime(year=2017, month=12, day=15),
        ],
        "Title": [
            "Star Wars: The Rise of Skywalker",
            "[red]Solo[/red]: A Star Wars Story",
            "Star Wars Ep. VIII: The Last Jedi",
        ],
        "Production Budget": ["$275,000,000", "$275,000,000", "$262,000,000"],
        "Box Office": ["$375,126,118", "$393,151,347", "$1,332,539,889"],
    }
    df = pd.DataFrame(sample_data)

    # Convert DataFrame to Rich Table and display
    table = df_to_rich_table(df)

    console.print("\n[bold]DataFrame to Rich Table Demo:[/bold]\n")
    console.print(table)
    console.print()
