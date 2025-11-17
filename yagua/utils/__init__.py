"""Yagua - Utility Functions Module.

This module provides utility functions for the yagua package, particularly
for formatting and displaying data in the command-line interface.

Available Utilities
-------------------
df_to_rich_table : function
    Convert pandas DataFrames to Rich Table objects for beautiful CLI output.

Purpose
-------
The utilities in this module are designed to enhance the user experience
when working with yagua's CLI by providing professional-looking, formatted
output for data tables and reports.

Examples
--------
>>> from yagua.utils import df_to_rich_table
>>> import pandas as pd
>>> df = pd.DataFrame({'test': ['test1', 'test2'], 'coverage': [85.5, 92.3]})
>>> table = df_to_rich_table(df, show_index=False)
>>> console.print(table)
"""

from .df2rt import df_to_rich_table

__all__ = ["df_to_rich_table"]
