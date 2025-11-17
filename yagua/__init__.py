"""Yagua - Tool for collecting and managing test information.

Yagua is a Python package for collecting and managing test information from
pytest-based projects. It provides tools to discover tests, collect coverage
metrics, and analyze test redundancy and uniqueness.

Main Components
---------------
main : function
    CLI entry point for the yagua command-line tool.
Project : class
    Main class for managing project databases and test information.
PytestSuite : class
    Test suite handler for pytest-based projects.
TestSuiteABC : class
    Abstract base class for implementing test suite handlers.

Examples
--------
Using the CLI:
    $ yagua create-project /path/to/project
    $ yagua collect-tests project.sqlite
    $ yagua collect-coverage project.sqlite
    $ yagua list-tests project.sqlite

Using the API:
    >>> from yagua import Project, PytestSuite
    >>> proj = Project.from_project_info(
    ...     name="my_project",
    ...     path="/path/to/project",
    ...     description="My test project",
    ...     db_path="qa.sqlite"
    ... )
    >>> suite = PytestSuite()
    >>> saved, updated = proj.collect_tests(suite)
    >>> coverage = proj.collect_coverage(suite)
"""

from .cli import main
from .project import Project
from .testsuites import PytestSuite, TestSuiteABC

__all__ = ["main", "Project", "PytestSuite", "TestSuiteABC"]


def read_db(path):
    """Open an existing project database.

    This is a convenience function that creates a Project instance
    from an existing database file path.

    Parameters
    ----------
    path : str or Path
        Path to an existing SQLite database cache file.

    Returns
    -------
    Project
        Project instance connected to the specified database.

    See Also
    --------
    Project : Main project management class.
    Project.from_project_info : Create a new project with metadata.

    Examples
    --------
    >>> from yagua import read_db
    >>> proj = read_db("project.sqlite")
    >>> print(proj.name)
    my_project
    """
    return Project(path)
