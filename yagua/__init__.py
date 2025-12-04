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
read_dir : function
    Convenience function to open an existing project work directory.
read_archive : function
    Convenience function to extract and open a project from an archive file.
"""

from .cli import main
from .io import read_archive, read_dir
from .project import Project
from .testsuites import PytestSuite, TestSuiteABC

__all__ = [
    "main",
    "Project",
    "PytestSuite",
    "TestSuiteABC",
    "read_dir",
    "read_archive",
]
