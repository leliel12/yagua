"""Yagua - Software entropy analysis through mutation testing.

Yagua is a Python package for collecting and managing test information from
pytest-based projects. Grounded in statistical mechanics, it approximates
software entropy by exploring the local neighborhood of the mutation graph—
the space of syntactic variants (mutants) around your implementation. This
provides a principled, computationally tractable approach to quantifying
test suite quality without enumerating all possible programs.

Main Components
---------------
main : function
    CLI entry point for the yagua command-line tool (session-based
    pipeline design).
Project : class
    Business logic layer for project operations with pipeline validation.
ProjectStore : class
    Data access layer for managing project data and test information.
PytestSuite : class
    Test suite handler for pytest-based projects.
TestSuiteABC : class
    Abstract base class for implementing test suite handlers.
read_dir : function
    Convenience function to open an existing project work directory
    (returns Project).
read_archive : function
    Convenience function to extract and open a project from an archive
    file (returns Project).
"""

from .cli import main
from .dal import ProjectStore
from .io import read_archive, read_dir
from .project import Project
from .testsuites import PytestSuite, TestSuiteABC

__all__ = [
    "main",
    "Project",
    "ProjectStore",
    "PytestSuite",
    "TestSuiteABC",
    "read_dir",
    "read_archive",
]
