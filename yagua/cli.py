"""
Yagua - CLI Interface.
"""

import inspect
import sys
from pathlib import Path

import typer

from .project import Project
from .testsuites import PytestSuite


# ============================================================================
# CLI MANAGER CLASS
# ============================================================================


def as_path(string):
    return Path(string).resolve()


class CLIManager:
    """CLI manager that exposes methods as typer subcommands.

    This class contains methods that are automatically registered as
    Typer commands through introspection. Each public method becomes
    a CLI subcommand.

    Methods
    -------
    collect
        Collect tests from a project using pytest.
    info
        Show project information from cache.
    list_tests
        List all tests for a project.
    """

    def create_project(
        self,
        project_path: str = typer.Argument(
            ...,
            help="Path to the project directory",
            parser=as_path,
        ),
        cache: str = typer.Argument(
            None,
            help="[CLAUDE COMPLETA]",
            parser=as_path,
        ),
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

        if not project_path.exists():
            typer.echo(
                f"Error: Project path does not exist: {project_path}",
                err=True,
            )
            raise typer.Exit(code=1)

        project_name = name or project_path.name
        cache = cache or as_path(project_path.name + ".sqlite")

        typer.echo(f"Creating empty cache for project: {project_name}")
        typer.echo(f"Cache file: {cache.name}")

        try:
            proj = Project.from_project_info(
                name=project_name,
                path=project_path,
                description=description,
                db_path=cache,
            )
        except Exception as err:
            typer.echo(str(err), err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Project created: {proj.name}")
        typer.echo(f"Path: {proj.path}")
        if proj.description:
            typer.echo(f"Description: {proj.description}")
        typer.echo("Cache initialized successfully")

    def collect(
        self,
        cache: str = typer.Argument(
            ...,
            help="[CLAUDE COMPLETA]",
            parser=as_path,
        ),
    ) -> None:

        if not cache.exists():
            typer.echo(
                f"Error: Project path does not exist: {cache}",
                err=True,
            )
            raise typer.Exit(code=1)

        with Project(
            db_path=cache,
        ) as proj:
            typer.echo(f"Using project: {proj.name} ({proj.path})")

            # Create test suite and collect tests
            suite = PytestSuite()
            saved_count, updated_count = proj.collect_tests(suite)

            total_tests = saved_count + updated_count
            if total_tests == 0:
                typer.echo("No tests collected.")
                raise typer.Exit(code=1)

            typer.echo(f"Collected {total_tests} tests")
            typer.echo(f"Saved {saved_count} new tests")
            if updated_count > 0:
                typer.echo(f"Updated {updated_count} existing tests")

    # def info(
    #     self,
    #     ctx: typer.Context,
    #     project_path: str = typer.Argument(
    #         ...,
    #         help="Path to the project directory",
    #     ),
    #     name: str = typer.Option(
    #         None,
    #         "-n",
    #         "--name",
    #         help="Project name (defaults to directory name)",
    #     ),
    # ) -> None:
    #     """Show project information from cache.

    #     This command displays information about the project stored in the
    #     cache, including its name, path, description, and test count.

    #     Parameters
    #     ----------
    #     ctx : typer.Context
    #         Typer context containing cache_path.
    #     project_path : str
    #         Path to the project directory.
    #     name : str, optional
    #         Project name (defaults to directory name).
    #     """
    #     cache_path = ctx.obj.cache_path
    #     project_path_obj = Path(project_path).resolve()
    #     project_name = name or project_path_obj.name

    #     with Project(
    #         cache_path=cache_path,
    #         name=project_name,
    #         path=str(project_path_obj),
    #     ) as proj:
    #         typer.echo("\nProject Information:")
    #         typer.echo("=" * 80)
    #         typer.echo(f"Name: {proj.project.name}")
    #         typer.echo(f"Path: {proj.project.path}")
    #         if proj.project.description:
    #             typer.echo(f"Description: {proj.project.description}")
    #         test_count = proj.project.tests.count()
    #         typer.echo(f"Tests: {test_count}")
    #         typer.echo("-" * 80)

    # def list_tests(
    #     self,
    #     ctx: typer.Context,
    #     project_path: str = typer.Argument(
    #         ...,
    #         help="Path to the project directory",
    #     ),
    #     name: str = typer.Option(
    #         None,
    #         "-n",
    #         "--name",
    #         help="Project name (defaults to directory name)",
    #     ),
    # ) -> None:
    #     """List all tests for a project.

    #     This command displays all tests associated with the project,
    #     including their file paths, suite names (if any), test names, and
    #     coverage information.

    #     Parameters
    #     ----------
    #     ctx : typer.Context
    #         Typer context containing cache_path.
    #     project_path : str
    #         Path to the project directory.
    #     name : str, optional
    #         Project name (defaults to directory name).
    #     """
    #     cache_path = ctx.obj.cache_path
    #     project_path_obj = Path(project_path).resolve()
    #     project_name = name or project_path_obj.name

    #     with Project(
    #         cache_path=cache_path,
    #         name=project_name,
    #         path=str(project_path_obj),
    #     ) as proj:
    #         tests = proj.list_tests()

    #         if not tests:
    #             typer.echo(f"No tests found for project '{project_name}'.")
    #             return

    #         typer.echo(f"\nTests for project '{project_name}':")
    #         typer.echo("=" * 80)

    #         for test in tests:
    #             if test.suite:
    #                 test_path = f"{test.file}::{test.suite}::{test.test}"
    #             else:
    #                 test_path = f"{test.file}::{test.test}"

    #             coverage_str = (
    #                 f"{test.coverage:.2f}%"
    #                 if test.coverage is not None
    #                 else "N/A"
    #             )
    #             typer.echo(f"{test_path} (coverage: {coverage_str})")

    #         typer.echo("-" * 80)
    #         typer.echo(f"Total: {len(tests)} tests")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


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


def _create_app(cli_manager):
    """Create and configure the Typer application.

    This function sets up the main Typer application instance and
    automatically registers all public methods from the CLI class as
    subcommands using introspection. This approach allows for clean
    separation of command logic while maintaining a simple
    registration mechanism.

    The application is configured with:
        - name: "yagua"
        - Global callback: _global_cache_callback (handles --cache option)
        - Auto-completion: Disabled
        - Commands: Dynamically registered from CLI class methods

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
    class are registered as commands. Each method should accept a
    typer.Context as its first parameter to access the global
    configuration.
    """
    app = typer.Typer(
        name="yagua",
        help="Yagua - Tool for collecting and managing test information",
        add_completion=False,
    )

    # Introspect CLI class and register methods as commands
    members = inspect.getmembers(cli_manager, predicate=inspect.ismethod)
    for name, method in members:
        if not name.startswith("_"):
            doc = _make_help(method)
            cmd_wrapper = app.command(name=name.replace("_", "-"), help=doc)
            cmd_wrapper(method)

    return app


# ============================================================================
# MAIN FUNCTION
# ============================================================================


def main():
    """Entry point for the Yagua CLI application."""
    # Show help if no arguments provided
    if len(sys.argv) == 1:
        sys.argv.append("--help")

    cli_manager = CLIManager()
    app = _create_app(cli_manager)
    app()
