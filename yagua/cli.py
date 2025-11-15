"""
Yagua - CLI Interface.

This module provides the command-line interface for yagua, a tool for
collecting and managing test information from pytest-based projects.
"""

import inspect
import sys
from pathlib import Path

import typer

from .project import Project
from .testsuites import PytestSuite


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


#: Reusable Typer argument definition for cache file path.
#:
#: This constant provides a consistent argument definition across all
#: CLI commands that require a cache file path. It ensures that:
#: - The argument is required (...)
#: - The path string is converted to a resolved Path object (parser=as_path)
#: - The help text and metavar are consistent across all commands
#:
#: Type: typer.Argument
_CACHE_ARGUMENT = typer.Argument(
    ...,
    help="Path to SQLite database file",
    parser=as_path,
    metavar="💾 Project Cache db",
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

    def _validate_cache_exists(self, cache):
        """Validate that cache file exists, exit with error if not.

        Parameters
        ----------
        cache : Path
            Path to cache file to validate.

        Raises
        ------
        typer.Exit
            If cache file does not exist.
        """
        if not cache.exists():
            typer.echo(
                f"❌ Error: Cache file does not exist: {cache}",
                err=True,
            )
            raise typer.Exit(code=1)

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
        cache: str = _CACHE_ARGUMENT,
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
            <project_name>.sqlite in the current directory.
        name : str, optional
            Project name. If not provided, uses the directory name.
        description : str, optional
            Project description.

        Raises
        ------
        typer.Exit
            If project path does not exist or cache file already exists.

        Examples
        --------
        Create cache with default name:
            $ yagua create-project /path/to/project

        Create cache with custom name and location:
            $ yagua create-project /path/to/project my_cache.sqlite \
                -n "My Project"
        """
        if not project_path.exists():
            typer.echo(
                f"❌ Error: Project path does not exist: {project_path}",
                err=True,
            )
            raise typer.Exit(code=1)

        project_name = name or project_path.name
        cache = cache or as_path(project_path.name + ".sqlite")

        typer.echo(f"📦 Creating empty cache for project: {project_name}")
        typer.echo(f"💾 Cache file: {cache.name}")

        try:
            proj = Project.from_project_info(
                name=project_name,
                path=project_path,
                description=description,
                db_path=cache,
            )
        except Exception as err:
            typer.echo(f"❌ {err}", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"✅ Project created: {proj.name}")
        typer.echo(f"📁 Path: {proj.path}")
        if proj.description:
            typer.echo(f"📝 Description: {proj.description}")
        typer.echo("✨ Cache initialized successfully (0 tests)")

    # ========================================================================
    # Public Commands - Test Management
    # ========================================================================

    def collect_tests(
        self,
        cache: str = _CACHE_ARGUMENT,
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

        Examples
        --------
        Collect tests from existing cache:
            $ yagua collect-tests my_project.sqlite

        Typical workflow:
            $ yagua create-project /path/to/project
            $ yagua collect-tests project.sqlite
        """
        self._validate_cache_exists(cache)

        with Project(
            db_path=cache,
        ) as proj:
            typer.echo(f"🔍 Using project: {proj.name} ({proj.path})")

            # Create test suite and collect tests
            suite = PytestSuite()
            saved_count, updated_count = proj.collect_tests(suite)

            total_tests = saved_count + updated_count
            if total_tests == 0:
                typer.echo("⚠️  No tests collected.")
                raise typer.Exit(code=1)

            typer.echo(f"✅ Collected {total_tests} tests")
            typer.echo(f"  💾 Saved {saved_count} new tests")
            if updated_count > 0:
                typer.echo(f"  🔄 Updated {updated_count} existing tests")

    def list_tests(
        self,
        cache: str = _CACHE_ARGUMENT,
        long: bool = typer.Option(
            False, "--long", "-l", help="Show all the information of the tests"
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

        Examples
        --------
        List all tests (compact view):
            $ yagua list-tests my_project.sqlite

        List tests with all information:
            $ yagua list-tests my_project.sqlite --long
            $ yagua list-tests my_project.sqlite -l
        """
        self._validate_cache_exists(cache)

        with Project(db_path=cache) as proj:
            tests = proj.get_tests_dataframe()

            if not long:

                ignore_columns = [
                    "id",
                    "project",
                    "test_id",
                    "created_at",
                    "modified_at",
                ]

                columns = [
                    col for col in tests.columns if col not in ignore_columns
                ]
                tests = tests[columns]

            if not len(tests):
                typer.echo(f"⚠️  No tests found for project '{proj.name}'.")
                return

            typer.echo(f"\n🧪 Tests for project '{proj.name}':")
            typer.echo("")

            typer.echo(tests)
            typer.echo("")
            typer.echo(f"📊 Total: {len(tests)} tests\n")

    # ========================================================================
    # Public Commands - Coverage Management
    # ========================================================================

    def collect_coverage(
        self,
        cache: str = _CACHE_ARGUMENT,
        force: bool = typer.Option(
            False,
            "--force",
            "-f",
            help="Force recalculation even if coverage exists",
        ),
    ) -> None:
        """Collect and store coverage information for the project.

        This command runs pytest with coverage enabled and stores the
        total coverage percentage in the project database.

        Parameters
        ----------
        cache : Path
            Path to existing SQLite cache file.
        force : bool, optional
            Force recalculation of coverage even if it already exists.

        Raises
        ------
        typer.Exit
            If cache file does not exist or no tests found.

        Examples
        --------
        Collect coverage:
            $ yagua collect-coverage my_project.sqlite

        Force recalculation:
            $ yagua collect-coverage my_project.sqlite --force
        """
        self._validate_cache_exists(cache)

        with Project(db_path=cache) as proj:
            if not proj.count_tests():
                typer.echo(f"⚠️  No tests found for project '{proj.name}'.")
                return

            if not (force or proj.coverage is None):
                typer.echo(
                    f"📊 Coverage already exists: {proj.coverage:.2f}%\n"
                    f"Use --force to recalculate."
                )
                raise typer.Exit(1)

            typer.echo(f"📊 Calculating coverage for: {proj.name}")
            suite = PytestSuite()
            cov = proj.collect_coverage(suite)
            typer.echo(f"💯 Total Coverage: {cov:.4f}%")

    # ========================================================================
    # Public Commands - Project Information
    # ========================================================================

    def info(
        self,
        cache: str = _CACHE_ARGUMENT,
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

        Examples
        --------
        Show project info:
            $ yagua info my_project.sqlite
        """
        self._validate_cache_exists(cache)

        with Project(db_path=cache) as proj:
            test_count = proj.count_tests()

            typer.echo("\n📊 Project Information -----------")
            typer.echo("")
            typer.echo(f"📝 Name: {proj.name}")
            typer.echo(f"📁 Path: {proj.path}")
            if proj.description:
                typer.echo(f"📄 Description: {proj.description}")
            if test_count:
                typer.echo(f"🧪 Tests: {test_count}")
            if proj.coverage:
                typer.echo(f"💯 Total Coverage: {proj.coverage:.4f}%")
            typer.echo("")


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

    # Introspect CLI class and register methods as commands
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
