"""
Yagua - Session-based CLI Interface.

This module provides a session-based command-line interface for yagua,
implementing a resumable pipeline pattern similar to cosmic-ray and mutmut.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import contextlib
import inspect
import sys
from pathlib import Path

import typer

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import project as project_module
from .dal import ProjectStore
from .project import PipelineError
from .utils.df2rt import df_to_rich_table


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

    Parameters
    ----------
    obj : object
        Object with a NumPy-style docstring.

    Returns
    -------
    str
        Summary portion of the docstring.
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

    Parameters
    ----------
    **kwargs
        Keyword arguments passed to typer.Argument.

    Returns
    -------
    typer.Argument
        Configured Typer argument for work directory path.
    """
    kwargs.setdefault("default", ...)
    kwargs.setdefault("help", "Path to work directory containing yagua.db")
    kwargs.setdefault("parser", as_path)
    kwargs.setdefault("metavar", "📁 Work Directory")
    return typer.Argument(**kwargs)


def _make_raise_errors_option(**kwargs):
    """Create a reusable Typer option for raise errors flag.

    Parameters
    ----------
    **kwargs
        Keyword arguments passed to typer.Option.

    Returns
    -------
    typer.Option
        Configured Typer option for raise errors flag.
    """
    default = kwargs.pop("default", False)
    kwargs.setdefault("help", "Raise exceptions instead of catching them")
    return typer.Option(default, "-r", "--raise-errors", **kwargs)


# ============================================================================
# CLI MANAGER CLASS
# ============================================================================


class CLIManager:
    """Session-based CLI manager for yagua.

    This class implements a resumable pipeline pattern where projects
    progress through stages: created -> tests_collected ->
    coverage_collected -> mutations_collected -> entropy_collected.

    Methods
    -------
    init
        Initialize a new yagua project.
    run
        Execute the pipeline (resumable).
    status
        Show pipeline progress as a table (fraction complete per step).
    tests_report
        Display per-test coverage and mutation metrics.
    entropy_report
        Display entropy dataframe ordered by mutants killed without.
    export
        Export work directory to archive.
    """

    def __init__(self):
        # Rich console for colored output
        self.console = Console()

    # ========================================================================
    # Private Methods
    # ========================================================================

    @contextlib.contextmanager
    def _use_project(self, work_dir):
        """Context manager to validate work directory and provide \
        Project.

        Parameters
        ----------
        work_dir : Path
            Path to work directory containing yagua.db.

        Yields
        ------
        Project
            Project instance with the store.

        Raises
        ------
        typer.Exit
            If work directory does not exist (exits with code 1).
        """
        if not work_dir.exists():
            self.console.print(
                Panel(
                    f"[red]Work directory does not exist:[/red]\n{work_dir}",
                    title="❌ Error",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)
        proj = project_module.from_work_dir(work_dir)
        try:
            self.console.print(
                f"[dim]🔍 Using project:[/dim] [cyan]{proj.store.name}[/cyan] "
                f"[dim]({proj.store.path})[/dim]\n"
            )
            yield proj
        finally:
            proj.store.close()

    # ========================================================================
    # Public Methods - Project Initialization
    # ========================================================================

    def init(
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
        mutation_timeout: float = typer.Option(
            50.0,
            "-mt",
            "--mutation-timeout",
            metavar="⏱️  SECONDS",
            help="Timeout in seconds for mutation testing",
        ),
        raise_errors: bool = _make_raise_errors_option(),
    ) -> None:
        """Initialize a new yagua project with database and work directory.

        This command creates a new yagua project by initializing a work
        directory containing the SQLite database (yagua.db) and all
        project metadata. The project starts in the 'created' pipeline
        step.

        Parameters
        ----------
        project_path : Path
            Path to the project directory to analyze.
        work_dir : Path, optional
            Path to work directory where yagua.db and temporary files will
            be stored. If not provided, defaults to
            _yagua_wd_<project_name>_ in the current directory.
        name : str, optional
            Project name. If not provided, uses the directory name.
        description : str, optional
            Project description.
        mutation_timeout : float, optional
            Timeout in seconds for mutation testing execution.
        raise_errors : bool, optional
            Raise exceptions instead of catching them. Default is False.

        Raises
        ------
        typer.Exit
            If project path does not exist or work directory already
            exists.
        """
        if not project_path.exists():
            if raise_errors:
                raise FileNotFoundError(
                    f"Project path does not exist: {project_path}"
                )
            self.console.print(
                Panel(
                    (
                        f"[red]Project path does not exist:[/red]"
                        f"\n{project_path}"
                    ),
                    title="❌ Error",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

        # Use provided name or default to directory name
        project_name = name or project_path.name

        # Use provided work_dir or default to _yagua_wd_<project_name>_
        work_dir = work_dir or as_path(f"_yagua_wd_{project_name}_")

        # Validate work directory does not exist
        if work_dir.exists():
            if raise_errors:
                raise FileExistsError(
                    f"Work directory already exists: {work_dir}"
                )
            self.console.print(
                Panel(
                    (
                        f"[red]Work directory already exists:[/red]"
                        f"\n{work_dir}"
                    ),
                    title="❌ Error",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

        self.console.print(
            "\n[bold cyan]📦 Initializing yagua project...[/bold cyan]\n"
        )

        try:
            manager = project_module.from_project_info(
                name=project_name,
                path=project_path,
                work_dir=work_dir,
                description=description,
                mutation_timeout=mutation_timeout,
            )
        except Exception as err:
            if raise_errors:
                raise
            self.console.print(
                Panel(
                    f"[red]{err}[/red]", title="❌ Error", border_style="red"
                )
            )
            raise typer.Exit(code=1)

        # Build success message
        info_lines = [
            "[bold green]✅ Project initialized successfully![/bold green]\n",
            f"[cyan]📝 Name:[/cyan] {manager.store.name}",
            f"[cyan]📁 Path:[/cyan] {manager.store.path}",
            f"[cyan]🗂️  Work Dir:[/cyan] {manager.store.work_dir}",
            f"[cyan]💾 Database:[/cyan] {manager.store.db_path}",
            f"[cyan]📊 Pipeline:[/cyan] {manager.store.pipeline_step}",
        ]

        if manager.store.description:
            info_lines.append(
                f"[cyan]🪪 Description:[/cyan] {manager.store.description}"
            )

        info_lines.append(
            f"[cyan]⏱️  Mutation Timeout:[/cyan] {manager.store.mutation_timeout}s"
        )

        info_lines.append(
            "\n[dim]💡 Next step:[/dim] " f"[cyan]yagua run {work_dir}[/cyan]"
        )

        self.console.print(
            Panel(
                "\n".join(info_lines),
                border_style="green",
                padding=(1, 2),
            )
        )

    # ========================================================================
    # Public Methods - Pipeline Execution
    # ========================================================================

    def run(
        self,
        work_dir: str = _make_work_dir_argument(),
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Force re-execution of steps",
        ),
        raise_errors: bool = _make_raise_errors_option(),
    ) -> None:
        """Execute the yagua pipeline (resumable).

        This command runs the analysis pipeline, automatically resuming
        from the last completed step. The pipeline consists of:
        1. Collect tests (pytest --collect-only)
        2. Collect coverage (per-test and without-test)
        3. Collect mutations (per-test and without-test)

        The pipeline state is tracked in the database, allowing you to
        resume from interruptions or failures.

        Mutations are evaluated in coverage_alone order (descending)
        to prioritize tests with higher individual coverage.

        Parameters
        ----------
        work_dir : Path
            Path to existing work directory containing yagua.db.
        force : bool
            Force re-execution of steps even if already completed.

        Raises
        ------
        typer.Exit
            If work directory does not exist or execution fails.
        """
        with self._use_project(work_dir) as proj:
            self.console.print(
                "[bold cyan]🚀 Running yagua pipeline...[/bold cyan]\n"
            )
            try:
                while step_method := proj.next_step():
                    step_name = step_method.__name__.replace("_", "-")
                    self._run_step(step_method, step_name, force)

                self.console.print(
                    "\n[bold green]✅ Pipeline completed successfully!"
                    "[/bold green]\n"
                )
            except Exception as err:
                # Mark failure using Project
                proj.mark_failed()

                if raise_errors:
                    raise

                self.console.print(
                    Panel(
                        f"[red]Pipeline failed:[/red]\n{err}",
                        title="❌ Error",
                        border_style="red",
                    )
                )
                raise typer.Exit(code=1)

    def _run_step(self, step, step_name, force):
        """Execute a single pipeline step with progress display.

        Parameters
        ----------
        step : callable
            Method to execute (collect_tests, collect_coverage, or
            collect_mutations).
        step_name : str
            Display name for the step.
        force : bool
            Force re-execution flag.

        Returns
        -------
        dict
            Result dictionary from the step execution.
        """
        self.console.print(f"[bold blue]🌟 {step_name}...[/bold blue]")

        # Create Rich Progress for the operation
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:

            task = progress.add_task("⚙️ Initializing...", total=None)

            def callback(current, total, test_id):
                if total:
                    progress.update(
                        task,
                        description=f"⚙️ Processing [dim]{current}/{total}[/dim]: {test_id}",  # noqa
                        total=total,
                        completed=current,
                    )
                else:
                    progress.update(
                        task, description=f"⚙️ Processing: {test_id}"
                    )
                progress.refresh()

        result = step(force=force, progress_callback=callback)

        # Display result summary - transform dict to displayable format
        result_items = []
        for key, value in result.items():
            # Skip values that are too large to display
            if len(str(value)) > 100:
                continue
            key = key.replace("_", "-")
            if isinstance(value, float):
                result_items.append(f"{key}={value:.3f}")
            else:
                result_items.append(f"{key}={value}")

        result_str = ", ".join(result_items)
        self.console.print(
            f"[green]💯[/green] {step_name} [bold]Done[/bold]: "
            f"[cyan]{result_str}[/cyan]\n"
        )

        return result

    # ========================================================================
    # Public Methods - Status & Reporting
    # ========================================================================

    def status(
        self,
        work_dir: str = _make_work_dir_argument(),
    ) -> None:
        """Show pipeline progress as a percentage table.

        Displays a table with one row per pipeline step and the
        fraction of work completed for that step, expressed as a
        percentage (e.g. 0% / 50% / 100%).

        Parameters
        ----------
        work_dir : Path
            Path to existing work directory containing yagua.db.

        Raises
        ------
        typer.Exit
            If work directory does not exist.
        """
        with self._use_project(work_dir) as proj:
            result = proj.get_pipeline_progress()
            result["progress"] = result["progress"].apply(lambda v: f"{v * 100}%")
            self.console.print(df_to_rich_table(result))


    def tests_report(
        self,
        work_dir: str = _make_work_dir_argument(),
        long: bool = typer.Option(
            False,
            "--long",
            "-l",
            help="Show all test information including timestamps and IDs",
        ),
        raise_errors: bool = _make_raise_errors_option(),
    ) -> None:
        """Display test results and metrics.

        This command shows all tests with their coverage and mutation
        metrics in a formatted table.

        Parameters
        ----------
        work_dir : Path
            Path to existing work directory containing yagua.db.
        long : bool, optional
            Show all test information including timestamps and IDs.
            Default is False.

        Raises
        ------
        typer.Exit
            If work directory does not exist.
        """
        with self._use_project(work_dir) as proj:
            try:
                result = proj.get_tests_report(include_internal=long)
            except (ValueError, PipelineError) as err:
                if raise_errors:
                    raise
                self.console.print(
                    Panel(
                        f"[yellow]{err}[/yellow]",
                        title="⚠️  Warning",
                        border_style="yellow",
                    )
                )
                raise typer.Exit(1)

            tests = result.tests_df
            tests_table = df_to_rich_table(tests, show_index=False)

            # Show summary info
            self.console.print()
            if result.coverage is not None:
                self.console.print(
                    f"💯 [bold green]Total coverage:[/bold green] "
                    f"[cyan]{result.coverage:.4f}[/cyan]"
                )
            if result.msr is not None:
                self.console.print(
                    f"🎯 [bold green]Survival rate:[/bold green] "
                    f"[cyan]{result.msr:.4f}[/cyan]"
                    f" ([cyan]⚰️  Killed: {result.mutants_killed}[/cyan], ",
                    f" [cyan]🛟 Survived: {result.mutants_survived}[/cyan], ",
                    f" [cyan]📍 Total: {result.mutants_number}[/cyan])",
                )
                print("-----")
                self.console.print(
                    f"☣️  [bold green]Mutation Active Test Ratio:[/bold green] "
                    f"[cyan]{result.mutation_active_test_ratio:.4f}[/cyan]"
                )
                self.console.print(
                    f"🪢 [bold green]Macrostate Tightness Index:[/bold green] "
                    f"[cyan]{result.macrostate_tightness_ratio:.4f}[/cyan]"
                )
            self.console.print()

            self.console.print("[bold cyan]🧪 Tests:[/bold cyan]\n")
            self.console.print(tests_table)
            self.console.print(
                f"\n[dim]📊 Total:[/dim] [bold]{result.tests_number}[/bold] "
                f"[dim]tests[/dim]\n"
            )

    def entropy_report(
        self,
        work_dir: str = _make_work_dir_argument(),
        raise_errors: bool = _make_raise_errors_option(),
    ) -> None:
        """Display the entropy dataframe ordered by mutants killed without.

        This command shows the entropy metrics for each test, ordered by
        mutants_killed_without ascending, excluding internal columns
        (tests_ids, created_at).

        Parameters
        ----------
        work_dir : Path
            Path to existing work directory containing yagua.db.

        Raises
        ------
        typer.Exit
            If work directory does not exist.
        """
        with self._use_project(work_dir) as proj:
            try:
                df = proj.store.get_entropy_dataframe()
            except Exception as err:
                if raise_errors:
                    raise
                self.console.print(
                    Panel(
                        f"[yellow]{err}[/yellow]",
                        title="⚠️  Warning",
                        border_style="yellow",
                    )
                )
                raise typer.Exit(1)

            drop = [c for c in ["tests_ids", "created_at"] if c in df.columns]
            df = df.drop(columns=drop)

            table = df_to_rich_table(df, show_index=False, float_fmt="{:.4f}")
            self.console.print()
            self.console.print(table)
            self.console.print()

    # ========================================================================
    # Public Methods - Export
    # ========================================================================

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
        raise_errors: bool = _make_raise_errors_option(),
    ) -> None:
        """Export work directory to an archive file.

        This command creates an archive file containing the entire work
        directory, including the yagua.db database and all temporary
        files. The archive format is automatically detected from the
        file extension.

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
        with self._use_project(work_dir) as proj:
            self.console.print(
                "\n[bold cyan]📦 Exporting work directory...[/bold cyan]\n"
            )

            try:
                archive_path = proj.export_project(output_path=output)
            except Exception as err:
                if raise_errors:
                    raise
                self.console.print(
                    Panel(
                        (
                            f"[red]Failed to export work directory:[/red]"
                            f"\n{err}"
                        ),
                        title="❌ Error",
                        border_style="red",
                    )
                )
                raise typer.Exit(code=1)

            # Build success message
            info_lines = [
                (
                    "[bold green]✅ Work directory exported successfully!"
                    "[/bold green]\n"
                ),
                f"[cyan]📦 Archive:[/cyan] {archive_path}",
                f"[cyan]📁 Source:[/cyan] {proj.store.work_dir}",
            ]

            self.console.print(
                Panel(
                    "\n".join(info_lines),
                    border_style="green",
                    padding=(1, 2),
                )
            )
            self.console.print()


# ============================================================================
# MAIN FUNCTION
# ============================================================================


def _create_app(cli_manager):
    """Create and configure the Typer application.

    This function sets up the main Typer application instance and
    automatically registers all public methods from the CLIManager class
    as subcommands using introspection.

    Parameters
    ----------
    cli_manager : CLIManager
        Instance of CLIManager class containing command methods.

    Returns
    -------
    typer.Typer
        Configured Typer application instance with all commands
        registered.
    """
    app = typer.Typer(
        name="yagua",
        help="🐕 Yagua - Session-based tool for test analysis",
        add_completion=True,
    )

    # Introspect CLIManager instance and register all public methods
    members = inspect.getmembers(cli_manager, predicate=inspect.ismethod)
    for name, method in members:
        if not name.startswith("_"):
            command_help = _make_help(method)
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
