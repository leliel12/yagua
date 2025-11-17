"""
Yagua - Tool for collecting and managing test information.
"""

from .cli import main
from .project import Project
from .testsuites import PytestSuite, TestSuiteABC

__all__ = ["main", "Project", "PytestSuite", "TestSuiteABC"]


def read_db(path):
    return Project(path)
