"""Show the entropy dataframe without test_ids or date columns."""

# =============================================================================
# IMPORTS
# =============================================================================

import sys
from pathlib import Path

from rich.console import Console

from yagua.dal import ProjectStore
from yagua.utils.df2rt import df_to_rich_table


# =============================================================================
# CONSTANTS
# =============================================================================

ORDERING_METHOD = "mutants_killed_without"
ASCENDING = True

DROP_COLS = ["tests_ids", "created_at"]


# =============================================================================
# MAIN
# =============================================================================


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <work_dir>")
        sys.exit(1)

    work_dir = Path(sys.argv[1])
    console = Console()

    store = ProjectStore(work_dir)
    try:
        df = store.get_entropy_dataframe(
            ordering_method=ORDERING_METHOD, ascending=ASCENDING
        )
    finally:
        store.close()

    drop = [c for c in DROP_COLS if c in df.columns]
    df = df.drop(columns=drop)

    table = df_to_rich_table(df, show_index=False, float_fmt="{:.4f}")
    console.print(table)


if __name__ == "__main__":
    main()

