#!/usr/bin/env python3
"""
QA Manager - Tool for collecting and managing test information.
"""

# ============================================================================
# IMPORTS
# ============================================================================

import inspect
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

import typer
from peewee import (
    Model,
    SqliteDatabase,
    CharField,
    FloatField,
    ForeignKeyField,
    IntegerField,
)


# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# Database instance will be initialized with user-provided path
db = SqliteDatabase(None)


# ============================================================================
# DATABASE MODELS
# ============================================================================


class BaseModel(Model):
    """Base model class that uses our database."""

    class Meta:
        database = db


class Project(BaseModel):
    """Project information table."""

    name = CharField(unique=True)
    path = CharField()
    description = CharField(null=True)


class Test(BaseModel):
    """Test information table."""

    project = ForeignKeyField(Project, backref="tests")
    file = CharField()
    suite = CharField(null=True)
    test = CharField()
    coverage = FloatField(null=True, default=None)

    class Meta:
        indexes = ((("project", "file", "suite", "test"), True),)  # Unique constraint


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def parse_test_line(line: str) -> Optional[Tuple[str, Optional[str], str]]:
    """
    Parse a pytest test line into components.

    Args:
        line: Test line in format 'file::Suite::test' or 'file::test'

    Returns:
        Tuple of (file, suite, test) or None if parsing fails
    """
    line = line.strip()
    if not line or not "::" in line:
        return None

    parts = line.split("::")
    if len(parts) == 2:
        # Format: file::test
        return (parts[0], None, parts[1])
    elif len(parts) == 3:
        # Format: file::Suite::test
        return (parts[0], parts[1], parts[2])
    else:
        return None


def collect_tests(project_path: Path) -> list:
    """
    Run pytest --collect-only -q and collect test information.

    Args:
        project_path: Path to the project directory

    Returns:
        List of tuples (file, suite, test)
    """
    try:
        result = subprocess.run(
            ["pytest", "--collect-only", "-q"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=True,
        )

        tests = []
        for line in result.stdout.splitlines():
            parsed = parse_test_line(line)
            if parsed:
                tests.append(parsed)

        return tests

    except subprocess.CalledProcessError as e:
        print(f"Error running pytest: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        return []
    except FileNotFoundError:
        print("Error: pytest not found. Please install pytest.", file=sys.stderr)
        return []


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================


def initialize_database(db_path: str):
    """
    Initialize the database and create tables.

    Args:
        db_path: Path to the SQLite database file
    """
    db.init(db_path)
    db.connect()
    db.create_tables([Project, Test], safe=True)


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
    collect
        Collect tests from a project using pytest.
    list_projects
        List all projects in the database.
    list_tests
        List all tests for a project.
    """

    def collect(
        self,
        ctx: typer.Context,
        project_path: str = typer.Argument(
            ...,
            help="Path to the project directory",
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
        """Collect tests from a project using pytest.

        This command runs pytest --collect-only -q to discover all tests
        in the project and stores them in the database.

        Parameters
        ----------
        ctx : typer.Context
            Typer context containing db_path.
        project_path : str
            Path to the project directory.
        name : str, optional
            Project name (defaults to directory name).
        description : str, optional
            Project description.

        Raises
        ------
        typer.Exit
            If project path does not exist or no tests collected.
        """
        db_path = ctx.obj.db_path
        project_path_obj = Path(project_path).resolve()

        if not project_path_obj.exists():
            typer.echo(
                f"Error: Project path does not exist: {project_path_obj}",
                err=True,
            )
            raise typer.Exit(code=1)

        typer.echo(f"Collecting tests from: {project_path_obj}")

        # Initialize database
        initialize_database(db_path)

        # Get or create project
        project_name = name or project_path_obj.name
        project, created = Project.get_or_create(
            name=project_name,
            defaults={
                "path": str(project_path_obj),
                "description": description,
            },
        )

        if not created:
            # Update existing project
            project.path = str(project_path_obj)
            if description:
                project.description = description
            project.save()

        # Collect tests
        tests = collect_tests(project_path_obj)

        if not tests:
            typer.echo("No tests collected.")
            db.close()
            raise typer.Exit(code=1)

        typer.echo(f"Collected {len(tests)} tests")

        # Save tests to database
        saved_count = 0
        updated_count = 0

        for file, suite, test in tests:
            test_obj, created = Test.get_or_create(
                project=project,
                file=file,
                suite=suite,
                test=test,
            )

            if created:
                saved_count += 1
            else:
                updated_count += 1

        typer.echo(f"✅ Saved {saved_count} new tests")
        if updated_count > 0:
            typer.echo(f"📝 Updated {updated_count} existing tests")

        db.close()

    def list_projects(self, ctx: typer.Context) -> None:
        """List all projects in the database.

        This command displays information about all projects stored in the
        database, including their names, paths, descriptions, and test counts.

        Parameters
        ----------
        ctx : typer.Context
            Typer context containing db_path.
        """
        db_path = ctx.obj.db_path
        initialize_database(db_path)

        projects = Project.select()

        if not projects:
            typer.echo("No projects found.")
            db.close()
            return

        typer.echo("\nProjects:")
        typer.echo("=" * 80)
        for project in projects:
            typer.echo(f"Name: {project.name}")
            typer.echo(f"Path: {project.path}")
            if project.description:
                typer.echo(f"Description: {project.description}")
            test_count = project.tests.count()
            typer.echo(f"Tests: {test_count}")
            typer.echo("-" * 80)

        db.close()

    def list_tests(
        self,
        ctx: typer.Context,
        project: str = typer.Argument(
            ...,
            help="Project name",
        ),
    ) -> None:
        """List all tests for a project.

        This command displays all tests associated with a specific project,
        including their file paths, suite names (if any), test names, and
        coverage information.

        Parameters
        ----------
        ctx : typer.Context
            Typer context containing db_path.
        project : str
            Project name.

        Raises
        ------
        typer.Exit
            If project is not found in the database.
        """
        db_path = ctx.obj.db_path
        initialize_database(db_path)

        try:
            project_obj = Project.get(Project.name == project)
        except Project.DoesNotExist:
            typer.echo(f"Error: Project '{project}' not found.", err=True)
            db.close()
            raise typer.Exit(code=1)

        tests = Test.select().where(Test.project == project_obj)

        if not tests:
            typer.echo(f"No tests found for project '{project}'.")
            db.close()
            return

        typer.echo(f"\nTests for project '{project}':")
        typer.echo("=" * 80)

        for test in tests:
            if test.suite:
                test_path = f"{test.file}::{test.suite}::{test.test}"
            else:
                test_path = f"{test.file}::{test.test}"

            coverage_str = (
                f"{test.coverage:.2f}%" if test.coverage is not None else "N/A"
            )
            typer.echo(f"{test_path} (coverage: {coverage_str})")

        typer.echo("-" * 80)
        typer.echo(f"Total: {tests.count()} tests")

        db.close()


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


def _global_cache_callback(
    ctx: typer.Context,
    cache: Path = typer.Option(
        (None if "--help" in sys.argv else ...),
        "--cache",
        help="Path to the SQLite database file (e.g., qaH.sqlite)",
        dir_okay=False,
    ),
):
    """Global configuration callback for Typer application.

    This function is called before any command and sets up the global
    configuration context. It stores the database path for use by
    all commands.

    Parameters
    ----------
    ctx : typer.Context
        Typer context to store application configuration.
    cache : Path
        Path to SQLite database file.
    """
    # Store db_path in context
    ctx.obj = type("Config", (), {"db_path": str(cache) if cache else None})()


def _create_app(cli_manager):
    """Create and configure the Typer application.

    This function sets up the main Typer application instance and
    automatically registers all public methods from the CLI class as
    subcommands using introspection. This approach allows for clean
    separation of command logic while maintaining a simple
    registration mechanism.

    The application is configured with:
        - name: "qa_manager"
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
        name="qa_manager",
        help="QA Manager - Tool for collecting and managing test information",
        add_completion=False,
        callback=_global_cache_callback,
    )

    # Introspect CLI class and register methods as commands
    members = inspect.getmembers(cli_manager, predicate=inspect.ismethod)
    for name, method in members:
        if not name.startswith("_"):
            doc = _make_help(method)
            # Convert method names like "list_projects" to "list-projects"
            cmd_name = name.replace("_", "-")
            cmd_wrapper = app.command(name=cmd_name, help=doc)
            cmd_wrapper(method)

    return app


# ============================================================================
# ENTRY POINT
# ============================================================================


def main():
    """Entry point for the QA Manager CLI application."""
    cli_manager = CLIManager()
    app = _create_app(cli_manager)
    app()


if __name__ == "__main__":
    main()
