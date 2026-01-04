"""Yagua - Tool for collecting and managing test information.

Yagua is a Python package for collecting and managing test information from
pytest-based projects. It provides tools to discover tests, collect coverage
metrics, and analyze test redundancy and uniqueness.

Main Components
---------------
main : function
    CLI entry point for the yagua command-line tool (original).
main2 : function
    CLI entry point for session-based yagua (new pipeline design).
Project : class
    Database access layer for managing project data and test information.
ProjectManager : class
    Business logic layer for project operations with pipeline validation.
PytestSuite : class
    Test suite handler for pytest-based projects.
TestSuiteABC : class
    Abstract base class for implementing test suite handlers.
read_dir : function
    Convenience function to open an existing project work directory
    (returns ProjectManager).
read_archive : function
    Convenience function to extract and open a project from an archive
    file (returns ProjectManager).
"""

from .cli import main
from .cli2 import main as main2
from .io import read_archive, read_dir
from .project import Project
from .project_manager import ProjectManager
from .testsuites import PytestSuite, TestSuiteABC

__all__ = [
    "main",
    "main2",
    "Project",
    "ProjectManager",
    "PytestSuite",
    "TestSuiteABC",
    "read_dir",
    "read_archive",
]
