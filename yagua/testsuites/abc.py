"""Yagua - Test Suite Abstract Base Class.

This module defines the abstract interface that all test suite handlers
must implement to integrate with yagua's test collection and coverage
analysis system.

Classes
-------
TestSuiteABC : ABC
    Abstract base class defining the required interface for test suite handlers.

Interface Contract
------------------
All test suite handlers must implement three abstract methods that return
consistent data structures:

1. get_tests(project_path) -> tuple[list, str, str, str, object]
   - Discovers all tests in a project
   - Returns: (tests_list, command, stdout, stderr, additional_data)

2. get_coverage(project_path, project_name) -> tuple[float, str, str, str, object]
   - Measures total coverage for all tests
   - Returns: (coverage_percent, command, stdout, stderr, additional_data)

3. get_coverage_for_tests(project_path, project_name, test_ids) -> tuple[float, str, str, str, object]
   - Measures coverage for specific test(s)
   - Returns: (coverage_percent, command, stdout, stderr, additional_data)

Return Value Format
-------------------
All methods return a consistent 5-tuple structure:
- Element 1: Primary result (test list or coverage percentage)
- Element 2: Command string that was executed
- Element 3: Standard output from command
- Element 4: Standard error from command
- Element 5: Additional framework-specific data

This format enables comprehensive audit logging through HistoryModel.

Notes
-----
The abstract methods use @abstractmethod decorator, ensuring that concrete
implementations must provide all required functionality. Attempting to
instantiate a subclass without implementing all abstract methods will raise
TypeError.

Examples
--------
Implementing a new test suite handler:

>>> from yagua.testsuites import TestSuiteABC
>>>
>>> class UnittestSuite(TestSuiteABC):
...     def get_tests(self, project_path):
...         # Implementation for unittest framework
...         tests = []  # Discover tests
...         return tests, "command", "stdout", "stderr", {}
...
...     def get_coverage(self, project_path, project_name):
...         # Implementation for coverage
...         return 85.5, "command", "stdout", "stderr", {}
...
...     def get_coverage_for_tests(self, project_path, project_name, test_ids):
...         # Implementation for specific tests
...         return 42.0, "command", "stdout", "stderr", {}
"""

from abc import ABC, abstractmethod


# ============================================================================
# TEST SUITE ABSTRACT BASE CLASS
# ============================================================================


class TestSuiteABC(ABC):
    """Abstract base class for test suite handlers.

    This class defines the interface that all test suite implementations
    must follow. Subclasses should implement methods for collecting tests
    and coverage information from different testing frameworks.

    All concrete implementations must provide three methods:
    - get_tests(): For test discovery
    - get_coverage(): For total coverage measurement
    - get_coverage_for_tests(): For selective coverage measurement

    The consistent return format across all methods enables yagua to
    store comprehensive audit logs of all operations in HistoryModel.

    See Also
    --------
    PytestSuite : Concrete implementation for pytest-based projects.
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
    def get_coverage_for_tests(
        self, project_path, project_name, test_ids
    ) -> tuple[float | None, str, str, str, object]:
        """Run specific test(s) with coverage and return coverage percentage.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run coverage on.
        project_name : str
            Name of the project/package to measure coverage for.
        test_ids : list[str]
            List of unique identifiers for tests to run (e.g., pytest node IDs).
            Can be a single-item list for isolated test coverage, or multiple
            items for combined coverage of specific tests.

        Returns
        -------
        coverage : float | None
            Coverage percentage (0-100) for the specified test(s), or None if
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
        This method provides flexible coverage collection:
        - Single test ([test_id]): Measures isolated test contribution
        - Multiple tests ([test_id1, test_id2, ...]): Measures combined coverage
        - All except one (query result): Enables coverage_without calculation

        This flexibility allows for both coverage_alone (single test) and
        coverage_without (all tests except one) metrics.
        """
        pass
