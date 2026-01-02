"""
Yagua - CLI Interface.

This module provides the command-line interface for yagua, a tool for
collecting and managing test information from pytest-based projects.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import contextlib
import inspect
import os
import sys
from pathlib import Path

import typer

from rich.console import Console
from rich.panel import Panel

from .project import Project
from .project_manager import ProjectManager, PipelineError
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


def _make_work_dir_argument(**kwargs):
    """Create a reusable Typer argument for work directory path.

    This factory function creates consistent work directory argument
    definitions across all CLI commands. It sets sensible defaults while
    allowing customization via keyword arguments.

    Parameters
    ----------
    **kwargs
        Keyword arguments passed to typer.Argument. Defaults are set for:
        - default: ... (required argument)
        - help: "Path to work directory containing yagua.db"
        - parser: as_path (converts to resolved Path)
        - metavar: "📁 Work Directory"

    Returns
    -------
    typer.Argument
        Configured Typer argument for work directory path.

    Notes
    -----
    The work directory contains:
    - yagua.db: SQLite database with project data
    - Temporary files from test/mutation frameworks
    """
    kwargs.setdefault("default", ...)
    kwargs.setdefault("help", "Path to work directory containing yagua.db")
    kwargs.setdefault("parser", as_path)
    kwargs.setdefault("metavar", "📁 Work Directory")
    return typer.Argument(**kwargs)


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
        Create a work directory with project metadata.
    collect_tests
        Collect tests from a project using pytest.
    list_tests
        List all tests for a project (with optional timestamp display).
    collect_coverage
        Collect and store coverage information.
    info
        Show project information from work directory.

    Notes
    -----
    All commands accept a work directory path as their first argument.
    Method names with underscores are converted to hyphenated command names
    (e.g., `collect_tests` becomes `collect-tests`).
    """

    # ========================================================================
    # Private Methods
    # ========================================================================

    @contextlib.contextmanager
    def _use_project(self, work_dir):
        """Context manager to validate work directory and provide ProjectManager.

        This method validates that the work directory exists, creates a Project
        instance and ProjectManager, displays project information, and ensures
        the database connection is properly closed when done.

        Parameters
        ----------
        work_dir : Path
            Path to work directory containing yagua.db.

        Yields
        ------
        ProjectManager
            ProjectManager instance with the project.

        Raises
        ------
        typer.Exit
            If work directory does not exist (exits with code 1).

        Notes
        -----
        This is the recommended way to access projects in CLI commands as it
        handles validation, error reporting, and cleanup automatically.
        """
        if not work_dir.exists():
            console.print(
                Panel(
                    f"[red]Work directory does not exist:[/red]\n{work_dir}",
                    title="❌ Error",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

        proj = Project(work_dir=work_dir)
        try:
            console.print(
                f"[dim]🔍 Using project:[/dim] [cyan]{proj.name}[/cyan] "
                f"[dim]({proj.path})[/dim]\n"
            )
            pm = ProjectManager(proj)
            yield pm
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
            metavar="📁 PATH",
        ),
        work_dir: str = _make_work_dir_argument(default=None),
        name: str = typer.Option(
            None,
            "-n",
            "--name",
            metavar="✏️  TEXT",
            help="Project name (defaults to directory name)",
        ),
        description: str = typer.Option(
            None,
            "-d",
            "--description",
            metavar="✏️  TEXT",
            help="Project description",
        ),
    ) -> None:
        """Create a new yagua project with database and work directory.

        This command initializes a new yagua project by creating a work
        directory containing the SQLite database (yagua.db) and all
        project metadata. The database is automatically created inside
        the work directory.

        Parameters
        ----------
        project_path : Path
            Path to the project directory to analyze.
        work_dir : Path, optional
            Path to work directory where yagua.db and temporary files will
            be stored. If not provided, defaults to _yagua_wd_<project_name>_
            in the current directory.
        name : str, optional
            Project name. If not provided, uses the directory name.
        description : str, optional
            Project description.

        Raises
        ------
        typer.Exit
            If project path does not exist or work directory already exists.
        """
        console.print(
            "\n[bold cyan]📦 Creating yagua project...[/bold cyan]\n"
        )

        # Validate inputs
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

        # Use provided work_dir or default to _yagua_wd_<project_name>_
        if work_dir is None:
            work_dir = as_path(f"_yagua_wd_{project_name}_")

        # Validate work directory does not exist
        if work_dir.exists():
            console.print(
                Panel(
                    f"[red]Work directory already exists:[/red]\n{work_dir}",
                    title="❌ Error",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

        try:
            proj = Project.from_project_info(
                name=project_name,
                path=project_path,
                work_dir=work_dir,
                description=description,
            )
        except Exception as err:
            console.print(
                Panel(
                    f"[red]{err}[/red]", title="❌ Error", border_style="red"
                )
            )
            raise typer.Exit(code=1)

        # Build success message
        info_lines = [
            f"[bold green]✅ Project created successfully![/bold green]\n",
            f"[cyan]📝 Name:[/cyan] {proj.name}",
            f"[cyan]📁 Path:[/cyan] {proj.path}",
            f"[cyan]🗂️  Work Dir:[/cyan] {proj.work_dir}",
            f"[cyan]💾 Database:[/cyan] {proj.db_path}",
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
        work_dir: str = _make_work_dir_argument(),
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Force recollection of tests",
        ),
    ) -> None:
        """Collect tests from a project using pytest.

        This command runs pytest --collect-only to discover all tests
        in the project and stores them in the yagua database. The work
        directory must already exist (use create-project first).

        Parameters
        ----------
        work_dir : Path
            Path to existing work directory containing yagua.db.
        force : bool
            Force recollection of tests even if already collected.

        Raises
        ------
        typer.Exit
            If work directory does not exist or no tests are collected.
        """
        with self._use_project(work_dir) as pm:
            if force or pm.project.count_tests() == 0:
                console.print(
                    "\n[bold cyan]🧪 Collecting tests...[/bold cyan]\n"
                )

            try:
                result = pm.collect_tests(force=force)
            except (ValueError, PipelineError) as err:
                console.print(
                    Panel(
                        f"[yellow]{err}[/yellow]\n\n"
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
                f"[cyan]📊 Total tests:[/cyan] {result['total_tests']}",
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
        work_dir: str = _make_work_dir_argument(),
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
        work_dir : Path
            Path to existing work directory containing yagua.db.
        long : bool, optional
            Show all test information including timestamps, IDs, and
            internal fields. Default is False.

        Raises
        ------
        typer.Exit
            If work directory does not exist.
        """
        with self._use_project(work_dir) as pm:
            try:
                info = pm.get_tests_info(include_internal=long)
            except (ValueError, PipelineError) as err:
                console.print(
                    Panel(
                        f"[yellow]{err}[/yellow]",
                        title="⚠️  Warning",
                        border_style="yellow",
                    )
                )
                return

            tests_table = df_to_rich_table(
                info["tests_df"], show_index=False
            )

            # Show coverage info if available
            if info["coverage"] is not None:
                console.print(
                    f"\n💯 [bold green]Total coverage:[/bold green] "
                    f"[cyan]{info['coverage']:.2f}%[/cyan]\n"
                )

            console.print("\n[bold cyan]🧪 Tests:[/bold cyan]\n")
            console.print(tests_table)
            console.print(
                f"\n[dim]📊 Total:[/dim] [bold]{info['total_count']}[/bold] "
                f"[dim]tests[/dim]\n"
            )

    # ========================================================================
    # Public Commands - Coverage Management
    # ========================================================================
    def collect_coverage(
        self,
        work_dir: str = _make_work_dir_argument(),
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
        work_dir : Path
            Path to existing work directory containing yagua.db.
        force : bool, optional
            Force recalculation of coverage even if it already exists.
            Default is False.

        Raises
        ------
        typer.Exit
            If work directory does not exist or no tests found.

        Notes
        -----
        Coverage collection can be time-consuming for large test suites
        as it runs each test individually and then all tests except each one.
        For N tests, this results in approximately 2N+1 test runs.

        After collecting coverage, the command automatically displays a summary
        of all tests with their coverage metrics using the list-tests command.
        """
        with self._use_project(work_dir) as pm:
            console.print("[bold blue]📊 Calculating coverage...[/bold blue]")

            try:
                # Phase 1: Calculate coverage for all tests combined
                console.print(
                    "[bold blue]🧪 Per-test coverage analysis..."
                    "[/bold blue]\n"
                )

                # Define progress callback
                def progress_callback(current, total, test_id):
                    proc_test_msg = (
                        f"  [dim][{current}/{total}][/dim] "
                        f"Processing {test_id}..."
                    )
                    console.print(proc_test_msg, end="\r")

                result = pm.collect_coverage(
                    force=force, progress_callback=progress_callback
                )

                # Clear progress message
                tests_count = len(result["tests_data"])
                if tests_count > 0:
                    proc_test_msg = (
                        f"  [dim][{tests_count}/{tests_count}][/dim] "
                        f"Processing..."
                    )
                    console.print(" " * len(proc_test_msg), end="\r")

                console.print(
                    "\n💯 [bold green]Total coverage:[/bold green] "
                    f"[cyan]{result['coverage']:.2f}%[/cyan]\n"
                )

            except (ValueError, PipelineError) as err:
                console.print(
                    Panel(
                        f"[yellow]{err}[/yellow]",
                        title="⚠️  Warning",
                        border_style="yellow",
                    )
                )
                raise typer.Exit(1)

        console.print(
            "[bold green]✅ Coverage collection complete!"
            "[/bold green]\n\n"
            "[dim]💡 Use[/dim] "
            f"[cyan]'yagua list-tests {work_dir}'[/cyan][dim] "
            "to view all coverage metrics[/dim]\n"
        )

    def collect_mutations(
        self,
        work_dir: str = _make_work_dir_argument(),
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Force recalculation even if mutations exist.",
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

        Tests are evaluated in coverage_uniqueness order (descending)
        to optimize mutation detection.

        Parameters
        ----------
        work_dir : Path
            Path to existing work directory containing yagua.db.
        force : bool, optional
            Force re-initialization and re-execution of mutations even if
            they already exist. Default is False.

        Raises
        ------
        typer.Exit
            If work directory does not exist, no coverage data exists,
            or coverage collection is incomplete.

        Notes
        -----
        Mutation testing can be very time-consuming for large codebases as it
        requires running the entire test suite against each generated mutant.

        Coverage data must be collected before running mutation analysis.
        Use the collect-coverage command first if coverage is missing.
        """
        with self._use_project(work_dir) as pm:
            console.print(
                "[bold blue]🧬 Running mutation analysis...[/bold blue]"
            )

            try:
                # Define progress callback
                def progress_callback(current, total, test_id):
                    proc_test_msg = (
                        f"  [dim][{current}/{total}][/dim] "
                        f"Processing {test_id}..."
                    )
                    console.print(proc_test_msg, end="\r")

                console.print(
                    "\n[bold blue]🧪 Per-test mutation analysis..."
                    "[/bold blue]\n"
                )

                result = pm.collect_mutations(
                    force=force,
                    progress_callback=progress_callback,
                )

                # Clear progress message
                tests_count = len(result["tests_data"])
                if tests_count > 0:
                    proc_test_msg = (
                        f"  [dim][{tests_count}/{tests_count}][/dim] "
                        f"Processing..."
                    )
                    console.print(" " * len(proc_test_msg), end="\r")

                console.print(
                    f"\n🧬 [bold green]Mutants Generated:[/bold green] "
                    f"[cyan]{result['mutants_number']}[/cyan]"
                )

                console.print(
                    f"\n🎯 [bold green]Survival Rate:[/bold green] "
                    f"[cyan]{result['msr']:.2f}%[/cyan]\n"
                )

            except (ValueError, PipelineError) as err:
                console.print(
                    Panel(
                        f"[yellow]{err}[/yellow]\n\n"
                        f"[dim]Run[/dim] [cyan]'yagua collect-coverage "
                        f"{work_dir}'[/cyan] [dim]first.[/dim]",
                        title="⚠️  Warning",
                        border_style="yellow",
                    )
                )
                raise typer.Exit(1)

        console.print(
            "[bold green]✅ Mutation collection complete![/bold green]\n\n"
            f"[dim]💡 Use[/dim] [cyan]'yagua list-tests {work_dir}'[/cyan]"
            "[dim] to view all mutation metrics[/dim]\n"
        )

    # ========================================================================
    # Public Commands - Project Information
    # ========================================================================

    def info(
        self,
        work_dir: str = _make_work_dir_argument(),
    ) -> None:
        """Show project information from database.

        This command displays information about the project stored in the
        yagua database, including its name, path, description, and test count.

        Parameters
        ----------
        work_dir : Path
            Path to existing work directory containing yagua.db.

        Raises
        ------
        typer.Exit
            If work directory does not exist.
        """
        with self._use_project(work_dir) as pm:
            info = pm.get_project_info()

            # Build info lines
            info_lines = [
                f"[cyan]📝 Name:[/cyan] {info['name']}",
                f"[cyan]📁 Path:[/cyan] {info['path']}",
                f"[cyan]🗂️  Work Dir:[/cyan] {info['work_dir']}",
                f"[cyan]💾 Database:[/cyan] {info['db_path']}",
            ]

            if info["description"]:
                info_lines.append(
                    f"[cyan]🪪 Description:[/cyan] {info['description']}"
                )

            if info["test_count"]:
                info_lines.append(
                    f"[cyan]🧪 Tests:[/cyan] {info['test_count']}"
                )

            if info["coverage"]:
                info_lines.append(
                    f"[cyan]💯 Coverage:[/cyan] "
                    f"[bold green]{info['coverage']:.2f}%[/bold green]"
                )

            if info["mutants_number"]:
                info_lines.append(
                    f"[cyan]🧬 Mutants:[/cyan] {info['mutants_number']}"
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

    def export(
        self,
        work_dir: str = _make_work_dir_argument(),
        output: str = typer.Option(
            None,
            "-o",
            "--output",
            help=(
                "Output path with extension "
                "(e.g., backup.zip, backup.tar.gz)"
            ),
            metavar="📁 PATH",
            parser=as_path,
        ),
    ) -> None:
        """Export work directory to an archive file.

        This command creates an archive file containing the entire work
        directory, including the yagua.db database and all temporary
        files. The archive format is automatically detected from the
        file extension. Supported formats: zip, tar, tar.gz (tgz),
        tar.bz2 (tbz2), tar.xz (txz).

        Parameters
        ----------
        work_dir : Path
            Path to existing work directory containing yagua.db.
        output : Path, optional
            Output path including the desired extension (e.g.,
            'backup.zip', 'backup.tar.gz'). If not provided, defaults to
            '<work_dir_name>.zip' in the current directory.

        Raises
        ------
        typer.Exit
            If work directory does not exist or export fails.
        """
        with self._use_project(work_dir) as pm:
            console.print(
                "\n[bold cyan]📦 Exporting work directory...[/bold cyan]\n"
            )

            try:
                archive_path = pm.export_project(output_path=output)
            except Exception as err:
                console.print(
                    Panel(
                        f"[red]Failed to export work directory:[/red]\n{err}",
                        title="❌ Error",
                        border_style="red",
                    )
                )
                raise typer.Exit(code=1)

            # Build success message
            info_lines = [
                "[bold green]✅ Work directory exported successfully!"
                "[/bold green]\n",
                f"[cyan]📦 Archive:[/cyan] {archive_path}",
                f"[cyan]📁 Source:[/cyan] {pm.project.work_dir}",
            ]

            console.print(
                Panel(
                    "\n".join(info_lines),
                    border_style="green",
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
