"""
Yagua - CLI Interface.

This module provides the command-line interface for yagua, a tool for
collecting and managing test information from pytest-based projects.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import contextlib
import enum
import inspect
import os
import sys
from pathlib import Path

import numpy as np
import typer

from rich.console import Console
from rich.panel import Panel

from .project import Project
from .models import TestModel
from .utils.df2rt import df_to_rich_table


# ============================================================================
# CONSTANTS
# ============================================================================

# Rich console for colored output
console = Console()


# ============================================================================
# PRIVATE HELPER FUNCTIONS
# ============================================================================


def as_path(string):
    """Convert string to resolved Path object.

    Parameters
    ----------
    string : str
        Path string to convert.

    Returns
    -------
    Path
        Resolved absolute Path object.
    """
    return Path(string).resolve()


def _make_help(obj) -> str:
    """Extract summary from a method's NumPy-style docstring.

    This function extracts the summary section from an object's
    docstring, which includes all content before the first section
    separator (a line of dashes). This is useful for generating
    concise help text for CLI commands.

    Parameters
    ----------
    obj : object
        Object with a NumPy-style docstring to extract help from.

    Returns
    -------
    str
        Summary portion of the docstring, or empty string if no
        docstring exists.

    Notes
    -----
    The function stops extracting at the first line that contains
    only dashes (e.g., "----------"), which marks the beginning of
    a formal section in NumPy-style docstrings.
    """
    lines = (obj.__doc__ or "").strip().splitlines()
    if lines:
        for lineno, line in enumerate(lines):
            line = line.strip()
            if line and not line.replace("-", ""):
                break
        last_line = lineno - 1
        lines = lines[:last_line]
    return "\n".join(lines)


def _coerce_na(value):
    """
    Coerces input values that are None or NaN (Not a Number) to None.

    This function is useful in data cleaning pipelines where you need a
    consistent representation for missing data points before further processing
    or storage (e.g., storing in a database that uses NULL).

    Parameters
    ----------
    value : Any
        The input value to check. Can be of various types
        (float, int, str, None, etc.).

    Returns
    -------
    Union[Any, None]
        Returns ``None`` if the input value is ``None`` or if it is a
        floating-point ``NaN`` value from numpy. Otherwise, the original value
        is returned unchanged.

    See Also
    --------
    numpy.isnan : Function used internally to check for NaN values.
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return value


def _make_cache_argument(**kwargs):
    """Create a reusable Typer argument for cache file path.

    This factory function creates consistent cache file argument definitions
    across all CLI commands. It sets sensible defaults while allowing
    customization via keyword arguments.

    Parameters
    ----------
    **kwargs
        Keyword arguments passed to typer.Argument. Defaults are set for:
        - default: ... (required argument)
        - help: "Path to SQLite database file"
        - parser: as_path (converts to resolved Path)
        - metavar: "💾 Project Cache db"

    Returns
    -------
    typer.Argument
        Configured Typer argument for cache file path.
    """
    kwargs.setdefault("default", ...)
    kwargs.setdefault("help", "Path to SQLite database file")
    kwargs.setdefault("parser", as_path)
    kwargs.setdefault("metavar", "💾 Project Cache db")
    return typer.Argument(**kwargs)


#: Enum for selecting test ordering column in collect-mutations command.
#:
#: This enum is dynamically generated from TestModel's coverage-related
#: fields and hybrid properties. It allows users to specify which coverage
#: metric should be used to prioritize test evaluation order during
#: mutation analysis.
#:
#: Members are created from all TestModel attributes starting with
#: "coverage_" (e.g., COVERAGE_ALONE, COVERAGE_WITHOUT, COVERAGE_IMPACT,
#: COVERAGE_UNIQUENESS, COVERAGE_REDUNDANCY, COVERAGE_OVERLAP).
_CollectMutationOrder = enum.StrEnum(
    "_CollectMutationOrder",
    {
        k.upper(): k
        for k, v in vars(TestModel).items()
        if k.startswith("coverage_")
    },
)

# ============================================================================
# CLI MANAGER CLASS
# ============================================================================


class CLIManager:
    """CLI manager that exposes methods as typer subcommands.

    This class contains methods that are automatically registered as
    Typer commands through introspection. Each public method becomes
    a CLI subcommand.

    Methods
    -------
    create_project
        Create an empty cache file with project metadata.
    collect_tests
        Collect tests from a project using pytest.
    list_tests
        List all tests for a project (with optional timestamp display).
    collect_coverage
        Collect and store coverage information.
    info
        Show project information from cache.

    Notes
    -----
    All commands accept a cache file path as their first argument.
    Method names with underscores are converted to hyphenated command names
    (e.g., `collect_tests` becomes `collect-tests`).
    """

    # ========================================================================
    # Private Methods
    # ========================================================================

    @contextlib.contextmanager
    def _use_project(self, cache):
        """Context manager to validate cache and provide Project instance.

        This method validates that the cache file exists, creates a Project
        instance, displays project information to the user, and ensures the
        database connection is properly closed when done.

        Parameters
        ----------
        cache : Path
            Path to cache file to validate and open.

        Yields
        ------
        Project
            Project instance connected to the cache database.

        Raises
        ------
        typer.Exit
            If cache file does not exist (exits with code 1).

        Notes
        -----
        This is the recommended way to access projects in CLI commands as it
        handles validation, error reporting, and cleanup automatically.
        """
        if not cache.exists():
            console.print(
                Panel(
                    f"[red]Cache file does not exist:[/red]\n{cache}",
                    title="❌ Error",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)
        proj = Project(db_path=cache)
        try:
            console.print(
                f"[dim]🔍 Using project:[/dim] [cyan]{proj.name}[/cyan] "
                f"[dim]({proj.path})[/dim]\n"
            )
            yield proj
        finally:
            proj.close()

    # ========================================================================
    # Public Methods - Project Creation
    # ========================================================================

    def create_project(
        self,
        project_path: str = typer.Argument(
            ...,
            help="Path to the project directory",
            parser=as_path,
        ),
        cache: str = _make_cache_argument(default=None),
        name: str = typer.Option(
            None,
            "-n",
            "--name",
            help="Project name (defaults to directory name)",
        ),
        description: str = typer.Option(
            None,
            "-d",
            "--description",
            help="Project description",
        ),
        work_path: str = typer.Option(
            None,
            "-w",
            "--work-path",
            help="Working directory for yagua operations (defaults to "
            "_yagua_wd_<project_name>_ in current directory)",
            parser=as_path,
        ),
    ) -> None:
        """Create an empty cache file with project metadata.

        This command initializes a new SQLite cache database with project
        metadata but no tests. Use this to create a project cache before
        running the collect command.

        Parameters
        ----------
        project_path : Path
            Path to the project directory.
        cache : Path, optional
            Path to SQLite cache file. If not provided, defaults to
            <project_name>.db in the current directory.
        name : str, optional
            Project name. If not provided, uses the directory name.
        description : str, optional
            Project description.
        work_path : Path, optional
            Working directory for yagua operations (coverage, mutations, etc.).
            If not provided, defaults to _yagua_wd_<project_name>_ in the
            current directory.

        Raises
        ------
        typer.Exit
            If project path does not exist or cache file already exists.
        """
        if not project_path.exists():
            console.print(
                Panel(
                    f"[red]Project path does not exist:[/red]\n{project_path}",
                    title="❌ Error",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

        # Use provided name or default to directory name
        project_name = name or project_path.name

        # Use provided cache path or default to <project_name>.db
        cache = cache or as_path(project_path.name + ".db")

        # Validate cache file does not exist
        if cache.exists():
            console.print(
                Panel(
                    f"[red]Cache file already exists:[/red]\n{cache}",
                    title="❌ Error",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

        # Use provided work path or default to _yagua_wd_<project_name>_
        work_path = work_path or as_path(f"_yagua_wd_{project_name}_")

        # Validate work path does not exist
        if work_path.exists():
            console.print(
                Panel(
                    f"[red]Working directory already exists:[/red]\n{work_path}",
                    title="❌ Error",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

        console.print("\n[bold cyan]📦 Creating project cache...[/bold cyan]\n")

        try:
            proj = Project.from_project_info(
                name=project_name,
                path=project_path,
                work_path=work_path,
                description=description,
                db_path=cache,
            )
            os.makedirs(work_path)
        except Exception as err:
            console.print(
                Panel(
                    f"[red]{err}[/red]",
                    title="❌ Error",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

        # Build success message
        info_lines = [
            f"[bold green]✅ Project created successfully![/bold green]\n",
            f"[cyan]📝 Name:[/cyan] {proj.name}",
            f"[cyan]📁 Path:[/cyan] {proj.path}",
            f"[cyan]🗂️  Working:[/cyan] {proj.work_path}",
            f"[cyan]💾 Cache:[/cyan] {cache}",
        ]

        if proj.description:
            info_lines.append(
                f"[cyan]🪪 Description:[/cyan] {proj.description}"
            )

        info_lines.append(f"\n[dim]✨ Cache initialized with 0 tests[/dim]")

        console.print(
            Panel(
                "\n".join(info_lines),
                border_style="green",
                padding=(1, 2),
            )
        )

    # ========================================================================
    # Public Commands - Test Management
    # ========================================================================

    def collect_tests(
        self,
        cache: str = _make_cache_argument(),
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Force recollection of tests",
        ),
    ) -> None:
        """Collect tests from a project using pytest.

        This command runs pytest --collect-only to discover all tests
        in the project and stores them in the cache database. The cache
        file must already exist (use create-project first).

        Parameters
        ----------
        cache : Path
            Path to existing SQLite cache file.

        Raises
        ------
        typer.Exit
            If cache file does not exist or no tests are collected.
        """
        with self._use_project(cache) as proj:

            total_tests = proj.count_tests()
            saved_count, updated_count = 0, 0

            if total_tests == 0 or force:
                console.print(
                    "\n[bold cyan]🧪 Collecting tests...[/bold cyan]\n"
                )
                saved_count, updated_count = proj.collect_tests()
                total_tests = saved_count + updated_count

            if total_tests == 0:
                console.print(
                    Panel(
                        "[yellow]No tests found in the project.[/yellow]\n\n"
                        "[dim]Make sure the project contains "
                        "pytest-compatible test files.[/dim]",
                        title="⚠️  Warning",
                        border_style="yellow",
                    )
                )
                raise typer.Exit(code=1)

            # Build success message
            info_lines = [
                "[bold green]✅ Tests collected successfully![/bold green]\n",
                f"[cyan]📊 Total tests:[/cyan] {total_tests}",
            ]

            console.print(
                Panel(
                    "\n".join(info_lines),
                    border_style="green",
                    padding=(1, 2),
                )
            )

    def list_tests(
        self,
        cache: str = _make_cache_argument(),
        long: bool = typer.Option(
            False,
            "--long",
            "-l",
            help="Show all the information of the tests",
        ),
    ) -> None:
        """List all tests for a project.

        This command displays all tests associated with the project,
        including their file paths, suite names (if any), test names, and
        coverage information. By default, internal columns (id, project,
        test_id, created_at, modified_at) are hidden unless --long is
        specified.

        Parameters
        ----------
        cache : Path
            Path to existing SQLite cache file.
        long : bool, optional
            Show all test information including timestamps, IDs, and
            internal fields. Default is False.

        Raises
        ------
        typer.Exit
            If cache file does not exist.
        """
        with self._use_project(cache) as proj:

            tests = proj.get_tests_dataframe()

            # Filter out internal columns unless --long is specified
            if not long:
                # Define columns to hide in compact view
                ignore_columns = [
                    "id",
                    "project",
                    "test_id",
                    "created_at",
                    "modified_at",
                ]

                # Keep only user-facing columns
                columns = [
                    col for col in tests.columns if col not in ignore_columns
                ]
                tests = tests[columns]

            # Check if any tests were found
            if not len(tests):
                console.print(
                    Panel(
                        f"[yellow]No tests found for project:[/yellow] "
                        f"[cyan]{proj.name}[/cyan]",
                        title="⚠️  Warning",
                        border_style="yellow",
                    )
                )
                return

            tests_table = df_to_rich_table(tests, show_index=False)

            # Show coverage info if available
            if proj.coverage is not None:
                console.print(
                    f"\n💯 [bold green]Total coverage:[/bold green] "
                    f"[cyan]{proj.coverage:.2f}%[/cyan]\n"
                )

            console.print("\n[bold cyan]🧪 Tests:[/bold cyan]\n")
            console.print(tests_table)
            console.print(
                f"\n[dim]📊 Total:[/dim] [bold]{len(tests)}[/bold] "
                f"[dim]tests[/dim]\n"
            )

    # ========================================================================
    # Public Commands - Coverage Management
    # ========================================================================
    def collect_coverage(
        self,
        cache: str = _make_cache_argument(),
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Force recalculation even if coverage exists",
        ),
    ) -> None:
        """Collect and store coverage information for the project.

        This command runs pytest with coverage enabled in three phases:
        1. Total project coverage (all tests)
        2. Per-test coverage (each test in isolation)
        3. Coverage without each test (all tests except one)

        The collected data enables calculation of test uniqueness,
        redundancy, and impact metrics.

        Parameters
        ----------
        cache : Path
            Path to existing SQLite cache file.
        force : bool, optional
            Force recalculation of coverage even if it already exists.
            Default is False.

        Raises
        ------
        typer.Exit
            If cache file does not exist or no tests found.

        Notes
        -----
        Coverage collection can be time-consuming for large test suites
        as it runs each test individually and then all tests except each one.
        For N tests, this results in approximately 2N+1 test runs.

        After collecting coverage, the command automatically displays a summary
        of all tests with their coverage metrics using the list-tests command.
        """
        with self._use_project(cache) as proj:

            console.print("[bold blue]📊 Calculating coverage...[/bold blue]")

            # Validate that there are tests to analyze
            if not proj.count_tests():
                typer.echo(f"⚠️  No tests found for project '{proj.name}'.")
                raise typer.Exit(1)

            # Phase 1: Calculate coverage for all tests combined
            if proj.coverage is None or force:
                proj.collect_coverage()
            console.print(
                "\n💯 [bold green]Total coverage:[/bold green] "
                f"[cyan]{proj.coverage:.2f}%[/cyan]\n"
            )

            # Phase 2 & 3: Calculate per-test coverage metrics
            console.print(
                "[bold blue]🧪 Per-test coverage analysis...[/bold blue]\n"
            )

            # Extract test IDs and existing coverage data from dataframe
            tests_ids = proj.get_tests_dataframe()[
                ["test_id", "coverage_alone", "coverage_without"]
            ].to_numpy()

            # Get total count for progress indicator
            tests_count = len(tests_ids)

            # Iterate through each test to calculate coverage metrics
            for idx, (test_id, cov_alone, cov_wo) in enumerate(tests_ids, 1):

                # Show progress to user
                proc_test_msg = (
                    f"  [dim][{idx}/{tests_count}][/dim] "
                    f"Processing {test_id}..."
                )
                console.print(proc_test_msg, end="\r")

                # Phase 2: Calculate coverage when running only this test
                # in isolation
                # This shows what this specific test covers on its own
                cov_alone = _coerce_na(cov_alone)
                if cov_alone is None or force:
                    cov_alone = proj.collect_coverage_for_test(test_id)

                # Phase 3: Calculate coverage when running all tests except
                # this one
                # This helps identify if this test adds unique coverage
                cov_wo = _coerce_na(cov_wo)
                if cov_wo is None or force:
                    cov_wo = proj.collect_coverage_without_test(test_id)

                # Clear progress message
                console.print(" " * len(proc_test_msg), end="\r")

        console.print(
            "[bold green]✅ Coverage collection complete!"
            "[/bold green]\n\n"
            f"[dim]💡 Use[/dim] [cyan]'yagua list-tests {cache.name}'[/cyan][dim] "
            "to view all coverage metrics[/dim]\n"
        )

    def collect_mutations(
        self,
        cache: str = _make_cache_argument(),
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Force recalculation even if mutations exist.",
        ),
        priority: _CollectMutationOrder = typer.Option(
            _CollectMutationOrder.COVERAGE_UNIQUENESS,
            "--priority",
            "-p",
            help="Column to determine test evaluation order.",
        ),
        ascending: bool = typer.Option(
            False,
            "--ascending",
            "-a",
            help="Sort tests in ascending order by priority column.",
        ),
    ) -> None:
        """Collect and analyze mutation testing data for the project.

        This command performs mutation testing analysis in two phases:

        Phase 1 - Mutation Initialization:
        - Initializes the mutation testing session
        - Counts the total number of mutants generated
        - Stores mutants_number in the project database

        Phase 2 - Mutation Execution:
        - Executes all mutations against the test suite
        - Calculates the mutation survival rate (% of mutants that survived)
        - Stores the survival rate (msr) in the project database

        The mutation score is calculated as (1 - survival_rate/100), where
        a lower survival rate indicates a more effective test suite.

        Parameters
        ----------
        cache : Path
            Path to existing SQLite cache file.
        force : bool, optional
            Force re-initialization and re-execution of mutations even if
            they already exist. Default is False.
        priority : _CollectMutationOrder, optional
            Column used to sort tests for evaluation order (for future
            per-test mutation analysis). Default is COVERAGE_UNIQUENESS.
        ascending : bool, optional
            Sort tests in ascending order. Default is False (descending).

        Raises
        ------
        typer.Exit
            If cache file does not exist, no coverage data exists,
            or coverage collection is incomplete.

        Notes
        -----
        Mutation testing can be very time-consuming for large codebases as it
        requires running the entire test suite against each generated mutant.

        Coverage data must be collected before running mutation analysis.
        Use the collect-coverage command first if coverage is missing.
        """
        with self._use_project(cache) as proj:

            console.print(
                "[bold blue]🧬 Running mutation analysis...[/bold blue]"
            )

            # Validate that coverage exists before running mutations
            if not proj.coverage:
                console.print(
                    Panel(
                        "[yellow]Coverage data is required before "
                        "running mutation analysis.[/yellow]\n\n"
                        f"[dim]Run[/dim] [cyan]'yagua collect-coverage "
                        f"{cache.name}'[/cyan] [dim]first.[/dim]",
                        title="⚠️  Warning",
                        border_style="yellow",
                    )
                )
                raise typer.Exit(1)

            # Phase 1: Initialize mutations and count mutants
            if proj.mutants_number is None or force:
                proj.collect_mutants(force=force)
            console.print(
                f"\n🧬 [bold green]Mutants Generated:[/bold green] "
                f"[cyan]{proj.mutants_number}[/cyan]"
            )

            # Phase 2: Execute mutations and calculate survival rate
            if proj.msr is None or force:
                proj.test_mutations(force)
            console.print(
                f"\n🎯 [bold green]Survival Rate:[/bold green] "
                f"[cyan]{proj.msr:.2f}%[/cyan]\n"
            )

            # Prepare dataframe with mutation and coverage columns
            priority_column = priority.value
            cov_columns = list(
                {"coverage_alone", "coverage_without", priority_column}
            )
            mutation_columns = ["test_id", "msr_alone", "msr_without"]

            tests_df = proj.get_tests_dataframe()[
                mutation_columns + cov_columns
            ]
            tests_df.sort_values(
                priority_column, ascending=ascending, inplace=True
            )

            # Validate that coverage collection is complete
            if tests_df[cov_columns].isna().to_numpy().any():
                console.print(
                    Panel(
                        "[yellow]Coverage collection appears to be "
                        "incomplete.[/yellow]\n\n"
                        "[dim]Some tests are missing coverage data. Run[/dim] "
                        f"[cyan]'yagua collect-coverage {cache.name} --force'"
                        "[/cyan] [dim]to recalculate.[/dim]",
                        title="⚠️  Warning",
                        border_style="yellow",
                    )
                )
                raise typer.Exit(1)

            # Phase 2 & 3: Calculate per-test mutation metrics
            console.print(
                "[bold blue]🧪 Per-test mutation analysis...[/bold blue]\n"
            )

            # Extract test data as numpy array for iteration
            tests_data = tests_df[mutation_columns].to_numpy()
            tests_count = len(tests_data)

            # Iterate through each test to calculate mutation metrics
            for idx, (test_id, msr_alone, msr_wo) in enumerate(tests_data, 1):

                # Show progress to user
                proc_test_msg = (
                    f"  [dim][{idx}/{tests_count}][/dim] "
                    f"Processing {test_id}..."
                )
                console.print(proc_test_msg, end="\r")

                # Phase 2: Calculate mutation score when running only this test
                # in isolation
                # This shows what mutants this specific test can detect on its
                # own
                msr_alone = _coerce_na(msr_alone)
                if msr_alone is None or force:
                    msr_alone = proj.collect_mutations_for_test(test_id)

                # Phase 3: Calculate mutation score when running all tests
                # except this one
                # This helps identify if this test detects unique mutants
                msr_wo = _coerce_na(msr_wo)
                if msr_wo is None or force:
                    msr_wo = proj.collect_mutations_without_test(test_id)

                # Clear progress message
                console.print(" " * len(proc_test_msg), end="\r")

        console.print(
            "[bold green]✅ Mutation collection complete![/bold green]\n\n"
            f"[dim]💡 Use[/dim] [cyan]'yagua list-tests {cache.name}'[/cyan]"
            "[dim] to view all mutation metrics[/dim]\n"
        )

    # ========================================================================
    # Public Commands - Project Information
    # ========================================================================

    def info(
        self,
        cache: str = _make_cache_argument(),
    ) -> None:
        """Show project information from cache.

        This command displays information about the project stored in the
        cache database, including its name, path, description, and test count.

        Parameters
        ----------
        cache : Path
            Path to existing SQLite cache file.

        Raises
        ------
        typer.Exit
            If cache file does not exist.
        """
        with self._use_project(cache) as proj:
            test_count = proj.count_tests()

            # Build info lines
            info_lines = [
                f"[cyan]📝 Name:[/cyan] {proj.name}",
                f"[cyan]📁 Path:[/cyan] {proj.path}",
                f"[cyan]💾 Cache:[/cyan] {cache}",
            ]

            if proj.description:
                info_lines.append(
                    f"[cyan]🪪 Description:[/cyan] {proj.description}"
                )

            if test_count:
                info_lines.append(f"[cyan]🧪 Tests:[/cyan] {test_count}")

            if proj.coverage:
                info_lines.append(
                    f"[cyan]💯 Coverage:[/cyan] "
                    f"[bold green]{proj.coverage:.2f}%[/bold green]"
                )

            if proj.mutants_number:
                info_lines.append(
                    f"[cyan]🧬 Mutants:[/cyan] {proj.mutants_number}"
                )

            console.print(
                Panel(
                    "\n".join(info_lines),
                    title="📊 Project Information",
                    border_style="blue",
                    padding=(1, 2),
                )
            )
            console.print()


# ============================================================================
# MAIN FUNCTION
# ============================================================================


def _create_app(cli_manager):
    """Create and configure the Typer application.

    This function sets up the main Typer application instance and
    automatically registers all public methods from the CLI class as
    subcommands using introspection. This approach allows for clean
    separation of command logic while maintaining a simple
    registration mechanism.

    Parameters
    ----------
    cli_manager : CLIManager
        Instance of CLIManager class containing command methods to
        register.

    Returns
    -------
    typer.Typer
        Configured Typer application instance with all commands
        registered and ready to use.

    Notes
    -----
    Only public methods (not starting with '_') from the CLIManager
    class are registered as commands. Method names with underscores
    are converted to hyphenated command names (e.g., create_project
    becomes create-project).
    """
    app = typer.Typer(
        name="yagua",
        help="🐕 Yagua - Tool for collecting and managing test information",
        add_completion=True,
    )

    # Introspect CLIManager instance and register all public methods
    # as commands
    members = inspect.getmembers(cli_manager, predicate=inspect.ismethod)
    for name, method in members:
        # Only register public methods (those not starting with underscore)
        if not name.startswith("_"):
            # Extract help text from method docstring
            command_help = _make_help(method)
            # Create command with hyphenated name
            # (e.g., collect_tests -> collect-tests)
            cmd_wrapper = app.command(
                name=name.replace("_", "-"), help=command_help
            )
            cmd_wrapper(method)

    return app


def main():
    """Entry point for the Yagua CLI application."""
    # Show help if no arguments provided
    if len(sys.argv) == 1:
        sys.argv.append("--help")

    cli_manager = CLIManager()
    app = _create_app(cli_manager)
    app()
