"""
Yagua - Session-based CLI Interface.

This module provides a session-based command-line interface for yagua,
implementing a resumable pipeline pattern similar to cosmic-ray and mutmut.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import contextlib
import enum
import inspect
import sys
from pathlib import Path

import typer

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .project import Project
from .project_manager import ProjectManager, PipelineError
from .models import TestModel
from .utils.df2rt import df_to_rich_table


# ============================================================================
# CONSTANTS
# ============================================================================

# Rich console for colored output
console = Console()


# ============================================================================
# PIPELINE STEPS ENUM
# ============================================================================


class PipelineStep(str, enum.Enum):
    """Pipeline execution steps."""

    CREATED = "created"
    TESTS_COLLECTED = "tests_collected"
    COVERAGE_COLLECTED = "coverage_collected"
    MUTATIONS_COLLECTED = "mutations_collected"
    COMPLETED = "completed"

    @classmethod
    def get_next_step(cls, current_step):
        """Get the next step in the pipeline.

        Parameters
        ----------
        current_step : PipelineStep
            Current pipeline step.

        Returns
        -------
        PipelineStep | None
            Next step in pipeline, or None if completed.
        """
        steps = [
            cls.CREATED,
            cls.TESTS_COLLECTED,
            cls.COVERAGE_COLLECTED,
            cls.MUTATIONS_COLLECTED,
            cls.COMPLETED,
        ]
        try:
            idx = steps.index(PipelineStep(current_step))
            if idx < len(steps) - 1:
                return steps[idx + 1]
            return None
        except (ValueError, IndexError):
            return None


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


#: Enum for selecting test ordering column in collect-mutations command.
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


class CLI2Manager:
    """Session-based CLI manager for yagua.

    This class implements a resumable pipeline pattern where projects
    progress through stages: created -> tests_collected ->
    coverage_collected -> mutations_collected -> completed.

    Methods
    -------
    init
        Initialize a new yagua project.
    run
        Execute the pipeline (resumable).
    status
        Show pipeline status and progress.
    report
        Display test results and metrics.
    export
        Export work directory to archive.
    """

    # ========================================================================
    # Private Methods
    # ========================================================================

    @contextlib.contextmanager
    def _use_project(self, work_dir):
        """Context manager to validate work directory and provide ProjectManager.

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

    def _get_pipeline_progress(self, pm):
        """Calculate pipeline progress statistics.

        Parameters
        ----------
        pm : ProjectManager
            ProjectManager instance.

        Returns
        -------
        dict
            Dictionary with progress statistics for each phase.
        """
        tests_df = pm.project.get_tests_dataframe()
        total_tests = len(tests_df)

        progress = {
            "total_tests": total_tests,
            "coverage_alone_complete": 0,
            "coverage_without_complete": 0,
            "mutations_alone_complete": 0,
            "mutations_without_complete": 0,
        }

        if total_tests == 0:
            return progress

        # Count completed coverage metrics
        progress["coverage_alone_complete"] = (
            tests_df["coverage_alone"].notna().sum()
        )
        progress["coverage_without_complete"] = (
            tests_df["coverage_without"].notna().sum()
        )

        # Count completed mutation metrics
        progress["mutations_alone_complete"] = (
            tests_df["msr_alone"].notna().sum()
        )
        progress["mutations_without_complete"] = (
            tests_df["msr_without"].notna().sum()
        )

        return progress

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

        Raises
        ------
        typer.Exit
            If project path does not exist or work directory already
            exists.
        """
        if not project_path.exists():
            console.print(
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
            console.print(
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

        console.print(
            "\n[bold cyan]📦 Initializing yagua project...[/bold cyan]\n"
        )

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
            "[bold green]✅ Project initialized successfully![/bold green]\n",
            f"[cyan]📝 Name:[/cyan] {proj.name}",
            f"[cyan]📁 Path:[/cyan] {proj.path}",
            f"[cyan]🗂️  Work Dir:[/cyan] {proj.work_dir}",
            f"[cyan]💾 Database:[/cyan] {proj.db_path}",
            f"[cyan]📊 Pipeline:[/cyan] {proj.pipeline_step}",
        ]

        if proj.description:
            info_lines.append(
                f"[cyan]🪪 Description:[/cyan] {proj.description}"
            )

        info_lines.append(
            "\n[dim]💡 Next step:[/dim] "
            f"[cyan]yagua run {work_dir}[/cyan]"
        )

        console.print(
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
        step: str = typer.Option(
            None,
            "--step",
            "-s",
            help=(
                "Execute specific step only (tests, coverage, mutations, all)"
            ),
        ),
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Force re-execution of steps",
        ),
        priority: _CollectMutationOrder = typer.Option(
            _CollectMutationOrder.COVERAGE_UNIQUENESS,
            "--priority",
            "-p",
            help="Column to determine test evaluation order for mutations.",
        ),
        ascending: bool = typer.Option(
            False,
            "--ascending",
            "-a",
            help="Sort tests in ascending order by priority column.",
        ),
    ) -> None:
        """Execute the yagua pipeline (resumable).

        This command runs the analysis pipeline, automatically resuming
        from the last completed step. The pipeline consists of:
        1. Collect tests (pytest --collect-only)
        2. Collect coverage (per-test and without-test)
        3. Collect mutations (per-test and without-test)

        The pipeline state is tracked in the database, allowing you to
        resume from interruptions or failures.

        Parameters
        ----------
        work_dir : Path
            Path to existing work directory containing yagua.db.
        step : str, optional
            Execute only a specific step: 'tests', 'coverage',
            'mutations', or 'all'. If not specified, resumes from
            current pipeline step.
        force : bool
            Force re-execution of steps even if already completed.
        priority : _CollectMutationOrder
            Column used to sort tests for mutation evaluation order.
        ascending : bool
            Sort tests in ascending order by priority column.

        Raises
        ------
        typer.Exit
            If work directory does not exist or execution fails.
        """
        with self._use_project(work_dir) as pm:
            console.print(
                "[bold cyan]🚀 Running yagua pipeline...[/bold cyan]\n"
            )

            # Determine which steps to run
            if step == "all" or force:
                steps_to_run = [
                    "tests",
                    "coverage",
                    "mutations",
                ]
            elif step:
                steps_to_run = [step]
            else:
                # Resume from current step
                current = PipelineStep(pm.project.pipeline_step)
                if current == PipelineStep.CREATED:
                    steps_to_run = ["tests", "coverage", "mutations"]
                elif current == PipelineStep.TESTS_COLLECTED:
                    steps_to_run = ["coverage", "mutations"]
                elif current == PipelineStep.COVERAGE_COLLECTED:
                    steps_to_run = ["mutations"]
                elif current == PipelineStep.MUTATIONS_COLLECTED:
                    steps_to_run = []
                else:
                    steps_to_run = []

            # Execute pipeline steps
            try:
                if "tests" in steps_to_run:
                    self._run_collect_tests(pm, force)

                if "coverage" in steps_to_run:
                    self._run_collect_coverage(pm, force)

                if "mutations" in steps_to_run:
                    self._run_collect_mutations(
                        pm, force, priority, ascending
                    )

                console.print(
                    "\n[bold green]✅ Pipeline completed successfully!"
                    "[/bold green]\n"
                )

            except Exception as err:
                # Mark failure using ProjectManager
                pm.mark_failed()

                console.print(
                    Panel(
                        f"[red]Pipeline failed:[/red]\n{err}",
                        title="❌ Error",
                        border_style="red",
                    )
                )
                raise typer.Exit(code=1)

    def _run_collect_tests(self, pm, force):
        """Execute test collection step.

        Parameters
        ----------
        pm : ProjectManager
            ProjectManager instance.
        force : bool
            Force recollection even if already done.
        """
        if pm.project.count_tests() == 0 or force:
            console.print("[bold blue]🧪 Collecting tests...[/bold blue]\n")

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

        console.print(
            f"[green]✓[/green] Tests collected: "
            f"[cyan]{result['total_tests']}[/cyan] tests\n"
        )

    def _run_collect_coverage(self, pm, force):
        """Execute coverage collection step.

        Parameters
        ----------
        pm : ProjectManager
            ProjectManager instance.
        force : bool
            Force recalculation even if already done.
        """
        console.print(
            "[bold blue]📊 Collecting coverage...[/bold blue]\n"
        )

        # Create Rich Progress for the operation
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Initialize progress tracking
            task = progress.add_task("Initializing...", total=None)

            # Progress callback for ProjectManager
            def progress_callback(current, total, test_id):
                if task is not None:
                    progress.update(
                        task,
                        description=(
                            f"Processing test {current}/{total}: {test_id}"
                        ),
                        total=total,
                        completed=current,
                    )

            try:
                result = pm.collect_coverage(
                    force=force, progress_callback=progress_callback
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
            f"[green]✓[/green] Total coverage: "
            f"[cyan]{result['coverage']:.2f}%[/cyan]\n"
        )
        console.print(
            f"[green]✓[/green] Coverage analysis complete "
            f"({len(result['tests_data'])} tests)\n"
        )

    def _run_collect_mutations(self, pm, force, priority, ascending):
        """Execute mutation collection step.

        Parameters
        ----------
        pm : ProjectManager
            ProjectManager instance.
        force : bool
            Force re-execution even if already done.
        priority : _CollectMutationOrder
            Column to sort tests by.
        ascending : bool
            Sort in ascending order.
        """
        console.print(
            "[bold blue]🧬 Collecting mutations...[/bold blue]\n"
        )

        # Create Rich Progress for the operation
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Initialize progress tracking
            task = progress.add_task("Initializing...", total=None)

            # Progress callback for ProjectManager
            def progress_callback(current, total, test_id):
                if task is not None:
                    progress.update(
                        task,
                        description=(
                            f"Processing test {current}/{total}: {test_id}"
                        ),
                        total=total,
                        completed=current,
                    )

            try:
                result = pm.collect_mutations(
                    force=force,
                    priority=priority.value if priority else None,
                    ascending=ascending,
                    progress_callback=progress_callback,
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
            f"[green]✓[/green] Mutants generated: "
            f"[cyan]{result['mutants_number']}[/cyan]\n"
        )
        console.print(
            f"[green]✓[/green] Survival rate: "
            f"[cyan]{result['msr']:.2f}%[/cyan]\n"
        )
        console.print(
            f"[green]✓[/green] Mutation analysis complete "
            f"({len(result['tests_data'])} tests)\n"
        )

    # ========================================================================
    # Public Methods - Status & Reporting
    # ========================================================================

    def status(
        self,
        work_dir: str = _make_work_dir_argument(),
    ) -> None:
        """Show project status and pipeline progress.

        This command displays the current state of the analysis pipeline,
        including which steps are completed and detailed progress for
        each phase.

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
            # Get progress statistics
            progress = self._get_pipeline_progress(pm)
            current_step = PipelineStep(pm.project.pipeline_step)

            # Build status table
            table = Table(title="Pipeline Status", show_header=True)
            table.add_column("Step", style="cyan")
            table.add_column("Status", style="bold")
            table.add_column("Progress", justify="right")

            # Tests collection
            if current_step.value == PipelineStep.CREATED.value:
                tests_status = "⏳ Pending"
            else:
                tests_status = (
                    f"✓ Complete ({progress['total_tests']} tests)"
                )
            table.add_row(
                "1. Collect Tests",
                tests_status,
                (
                    f"{progress['total_tests']}"
                    if progress["total_tests"]
                    else "-"
                ),
            )

            # Coverage collection
            if current_step.value in [
                PipelineStep.CREATED.value,
                PipelineStep.TESTS_COLLECTED.value,
            ]:
                coverage_status = "⏳ Pending"
                cov_progress = "-"
            elif (
                current_step.value
                == PipelineStep.COVERAGE_COLLECTED.value
                or progress["coverage_alone_complete"]
                == progress["total_tests"]
            ):
                coverage_status = "✓ Complete"
                cov_progress = (
                    f"{progress['coverage_alone_complete']}/"
                    f"{progress['total_tests']}"
                )
            else:
                coverage_status = "🔄 In Progress"
                cov_progress = (
                    f"{progress['coverage_alone_complete']}/"
                    f"{progress['total_tests']}"
                )
            table.add_row("2. Collect Coverage", coverage_status, cov_progress)

            # Mutation collection
            if current_step.value in [
                PipelineStep.CREATED.value,
                PipelineStep.TESTS_COLLECTED.value,
                PipelineStep.COVERAGE_COLLECTED.value,
            ]:
                mutations_status = "⏳ Pending"
                mut_progress = "-"
            elif (
                current_step.value
                == PipelineStep.MUTATIONS_COLLECTED.value
                or progress["mutations_alone_complete"]
                == progress["total_tests"]
            ):
                mutations_status = "✓ Complete"
                mut_progress = (
                    f"{progress['mutations_alone_complete']}/"
                    f"{progress['total_tests']}"
                )
            else:
                mutations_status = "🔄 In Progress"
                mut_progress = (
                    f"{progress['mutations_alone_complete']}/"
                    f"{progress['total_tests']}"
                )
            table.add_row(
                "3. Collect Mutations", mutations_status, mut_progress
            )

            console.print()
            console.print(table)
            console.print()

            # Summary information
            info_lines = [
                f"[cyan]📊 Current Step:[/cyan] {current_step.value}",
            ]

            if pm.project.coverage is not None:
                info_lines.append(
                    f"[cyan]💯 Coverage:[/cyan] {pm.project.coverage:.2f}%"
                )

            if pm.project.mutants_number is not None:
                info_lines.append(
                    f"[cyan]🧬 Mutants:[/cyan] {pm.project.mutants_number}"
                )

            if pm.project.msr is not None:
                info_lines.append(
                    f"[cyan]🎯 Survival Rate:[/cyan] {pm.project.msr:.2f}%"
                )

            if pm.project.failed_at:
                info_lines.append(
                    f"[yellow]⚠️  Last Failure:[/yellow] {pm.project.failed_at}"
                )

            console.print(Panel("\n".join(info_lines), border_style="blue"))

            # Next step suggestion
            if current_step != PipelineStep.COMPLETED:
                console.print(
                    f"\n[dim]💡 Next:[/dim] [cyan]yagua run "
                    f"{work_dir}[/cyan]\n"
                )
            else:
                console.print(
                    f"\n[dim]💡 View results:[/dim] [cyan]yagua report "
                    f"{work_dir}[/cyan]\n"
                )

    def report(
        self,
        work_dir: str = _make_work_dir_argument(),
        long: bool = typer.Option(
            False,
            "--long",
            "-l",
            help="Show all test information including timestamps and IDs",
        ),
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
        with self._use_project(work_dir) as pm:
            try:
                result = pm.get_tests_info(include_internal=long)
            except (ValueError, PipelineError) as err:
                console.print(
                    Panel(
                        f"[yellow]{err}[/yellow]",
                        title="⚠️  Warning",
                        border_style="yellow",
                    )
                )
                raise typer.Exit(1)

            tests = result["tests_df"]
            tests_table = df_to_rich_table(tests, show_index=False)

            # Show summary info
            console.print()
            if result["coverage"] is not None:
                console.print(
                    f"💯 [bold green]Total coverage:[/bold green] "
                    f"[cyan]{result['coverage']:.2f}%[/cyan]"
                )
            if pm.project.msr is not None:
                console.print(
                    f"🎯 [bold green]Survival rate:[/bold green] "
                    f"[cyan]{pm.project.msr:.2f}%[/cyan]"
                )
            console.print()

            console.print("[bold cyan]🧪 Tests:[/bold cyan]\n")
            console.print(tests_table)
            console.print(
                f"\n[dim]📊 Total:[/dim] [bold]{result['total_count']}[/bold] "
                f"[dim]tests[/dim]\n"
            )

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
        with self._use_project(work_dir) as pm:
            console.print(
                "\n[bold cyan]📦 Exporting work directory...[/bold cyan]\n"
            )

            try:
                archive_path = pm.export_project(output_path=output)
            except Exception as err:
                console.print(
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
    subcommands using introspection.

    Parameters
    ----------
    cli_manager : CLI2Manager
        Instance of CLI2Manager class containing command methods.

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

    # Introspect CLI2Manager instance and register all public methods
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
    """Entry point for the Yagua CLI2 application."""
    # Show help if no arguments provided
    if len(sys.argv) == 1:
        sys.argv.append("--help")

    cli_manager = CLI2Manager()
    app = _create_app(cli_manager)
    app()
