"""
Yagua - DataFrame to Rich Table Converter.

This module provides utilities to convert pandas DataFrames into
Rich Table objects for beautiful terminal output.

Source
------
Based on: https://gist.github.com/neelabalan/33ab34cf65b43e305c3f12ec6db05938
"""

from datetime import datetime
from typing import Optional

import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table


# ============================================================================
# CONSTANTS
# ============================================================================

console = Console()


# ============================================================================
# PUBLIC FUNCTIONS
# ============================================================================


def df_to_rich_table(
    pandas_dataframe: pd.DataFrame,
    show_index: bool = True,
    index_name: Optional[str] = None,
    header_style: str="bold magenta",
) -> Table:
    """Convert a pandas DataFrame into a Rich Table object.

    This function creates a styled Rich Table from a pandas DataFrame,
    preserving the data structure and adding visual formatting for
    terminal display. The table uses alternating row styles and a
    simple header box for clean presentation.

    Parameters
    ----------
    pandas_dataframe : pd.DataFrame
        A Pandas DataFrame to be converted to a Rich Table.
    show_index : bool, optional
        If True, add a column with row indices to the table.
        Defaults to True.
    index_name : str, optional
        The column name to give to the index column. If None,
        the index column will have no header. Defaults to None.

    Returns
    -------
    Table
        A Rich Table instance populated with the DataFrame values,
        styled with alternating row colors and a simple header box.

    Examples
    --------
    >>> import pandas as pd
    >>> from yagua.utils import df_to_rich_table
    >>> df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    >>> table = df_to_rich_table(df, show_index=True, index_name='#')
    >>> console.print(table)

    >>> # Without index
    >>> table = df_to_rich_table(df, show_index=False)
    >>> console.print(table)

    Notes
    -----
    - The table uses 'bold magenta' style for headers
    - Rows alternate between normal and dim styles
    - Uses SIMPLE_HEAD box style for clean appearance
    - All values are converted to strings for display
    """

    # Initiate a Table instance to be modified
    rich_table = Table(show_header=True, header_style=header_style)

    # Modify the table instance to have the data from the DataFrame
    if show_index:
        index_name = str(index_name) if index_name else ""
        rich_table.add_column(index_name)

    for column in pandas_dataframe.columns:
        rich_table.add_column(str(column))

    for index, value_list in enumerate(pandas_dataframe.values.tolist()):
        row = [str(index)] if show_index else []
        row += [str(x) for x in value_list]
        rich_table.add_row(*row)

    # Update the style of the table
    rich_table.row_styles = ["none", "dim"]
    rich_table.box = box.SIMPLE_HEAD

    return rich_table


if __name__ == "__main__":
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

    # convert to ritch table
    table = df_to_rich_table(df)

    console.print(table)
