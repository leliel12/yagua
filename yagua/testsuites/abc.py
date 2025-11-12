"""
Yagua - Test Suite Abstract Base Class.

This module defines the abstract interface that all test suite handlers
must implement.
"""

from abc import ABC, abstractmethod


# ============================================================================
# TEST SUITE ABSTRACT BASE CLASS
# ============================================================================


class TestSuiteABC(ABC):
    """
    Abstract base class for test suite handlers.

    This class defines the interface that all test suite implementations
    must follow. Subclasses should implement methods for collecting tests
    and optionally coverage information from different testing frameworks.
    """

    # ========================================================================
    # Abstract Methods
    # ========================================================================

    @abstractmethod
    def get_tests(self, project_path) -> list[tuple[str, str | None, str]]:
        """Collect all tests from a project.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory.

        Returns
        -------
        list[tuple[str, str | None, str]]
            List of tuples (file, suite, test) for each test found.
            The suite element can be None if the test is not part of a
            test class/suite.
        """
        pass

    @abstractmethod
    def get_coverage(self, project_path, project_name) -> float | None:
        """Run tests with coverage and return the total coverage percentage.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run coverage on.
        project_name : str
            Name of the project/package to measure coverage for.

        Returns
        -------
        float | None
            Total coverage percentage (0-100) or None if coverage could not
            be determined.
        """
        pass
