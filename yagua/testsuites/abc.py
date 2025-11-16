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
    def get_tests(
        self, project_path
    ) -> tuple[list[tuple[str, str | None, str, str]], str, str, str, object]:
        """Collect all tests from a project.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory.

        Returns
        -------
        tests : list[tuple[str, str | None, str, str]]
            List of tuples (file, suite, test, test_id) for each test found.
            - file: Test file path relative to project root
            - suite: Test suite/class name (None if standalone function)
            - test: Test function name
            - test_id: Unique test identifier (e.g., pytest node ID)
        command : str
            The command that was executed to collect tests.
        stdout : str
            Standard output from the command execution.
        stderr : str
            Standard error output from the command execution.
        data : object
            Additional data from the collection process (framework-specific).

        Notes
        -----
        The return tuple provides complete information about the test
        collection process, allowing the caller to log the command executed
        and store execution details (stdout, stderr, and additional data)
        for audit purposes.
        """
        pass

    @abstractmethod
    def get_coverage(
        self, project_path, project_name
    ) -> tuple[float | None, str, str, str, object]:
        """Run tests with coverage and return the total coverage percentage.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run coverage on.
        project_name : str
            Name of the project/package to measure coverage for.

        Returns
        -------
        coverage : float | None
            Total coverage percentage (0-100) or None if coverage could not
            be determined.
        command : str
            The command that was executed to collect coverage.
        stdout : str
            Standard output from the command execution.
        stderr : str
            Standard error output from the command execution.
        data : object
            Additional coverage data (e.g., JSON coverage report).

        Notes
        -----
        The return tuple provides complete information about the coverage
        collection process, allowing the caller to log the command executed
        and store execution details (stdout, stderr, and additional data) for
        audit purposes.
        """
        pass

    @abstractmethod
    def get_coverage_for_test(
        self, project_path, project_name, test_id
    ) -> tuple[float | None, str, str, str, object]:
        """Run a specific test with coverage and return its coverage percentage.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run coverage on.
        project_name : str
            Name of the project/package to measure coverage for.
        test_id : str
            Unique identifier for the test to run (e.g., pytest node ID).

        Returns
        -------
        coverage : float | None
            Coverage percentage (0-100) for this specific test, or None if
            coverage could not be determined.
        command : str
            The command that was executed to collect coverage.
        stdout : str
            Standard output from the command execution.
        stderr : str
            Standard error output from the command execution.
        data : object
            Additional coverage data (e.g., JSON coverage report).

        Notes
        -----
        This method runs a single test in isolation to determine what
        code coverage it provides when executed alone. This is useful for
        understanding the individual contribution of each test to overall
        coverage.
        """
        pass
