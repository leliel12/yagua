"""Yagua - Test Suite Abstract Base Class.

This module defines the abstract interface that all test suite handlers
must implement to integrate with yagua's test collection and coverage
analysis system.

Classes
-------
SuiteRunResult : dataclass
    Structured result from a test suite execution containing the value,
    command, status code, stdout, stderr, and additional data.
SuiteRunResultError : Exception
    Exception raised when a suite run fails (non-zero exit status).
TestSuiteABC : ABC
    Abstract base class defining the required interface for test suite
    handlers.

Interface Contract
------------------
All test suite handlers must implement three abstract methods that return
SuiteRunResult instances or compatible tuple structures:

1. get_tests(project_path) -> SuiteRunResult
   - Discovers all tests in a project
   - Returns result with tests_list as value

2. get_coverage(project_path, project_name) -> SuiteRunResult
   - Measures total coverage for all tests
   - Returns result with coverage_percent as value

3. get_coverage_for_tests(project_path, project_name, test_ids)
   -> SuiteRunResult
   - Measures coverage for specific test(s)
   - Returns result with coverage_percent as value

Return Value Format
-------------------
Methods can return either SuiteRunResult instances or 5-tuple structures:
- value: Primary result (test list or coverage percentage)
- command: Command string that was executed
- status_code: Exit status (0 = success, non-zero = error)
- stdout: Standard output from command
- stderr: Standard error from command
- result: Additional framework-specific data

This format enables comprehensive audit logging through HistoryModel.

Notes
-----
The abstract methods use @abstractmethod decorator, ensuring that concrete
implementations must provide all required functionality. Attempting to
instantiate a subclass without implementing all abstract methods will raise
TypeError.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


# ============================================================================
# EXCEPTIONS
# ============================================================================


class SuiteRunResultError(Exception):
    """Exception raised when a test suite command fails.

    This exception is raised by SuiteRunResult.raise_if_error() when the
    suite execution returns a non-zero exit status code, indicating an
    error occurred during test collection, execution, or coverage
    measurement.

    Parameters
    ----------
    status_code : int
        The non-zero exit status code from the failed command.
    stderr : str
        The standard error output from the failed command, containing
        error messages and diagnostic information.

    Attributes
    ----------
    status_code : int
        The exit status code that triggered the exception.
    stderr : str
        The captured error output.

    See Also
    --------
    SuiteRunResult : The dataclass that raises this exception.
    """

    def __init__(self, result):
        """Initialize the exception with status code and error output.

        """
        self.result = result
        super().__init__(f"{result.command} - Exit Code {result.status_code}")


# ============================================================================
# TEST SUITE RESULT DATACLASS
# ============================================================================


@dataclass(frozen=True)
class _SuiteRunResult:
    """Structured result from a test suite execution.

    This dataclass provides a standardized format for capturing the complete
    outcome of running test suite commands (e.g., test collection, coverage
    measurement). It encapsulates both the primary result value and all
    execution metadata necessary for debugging, logging, and audit trails.

    Attributes
    ----------
    value : object
        The primary result value from the operation. Type varies by operation:
        - For get_tests(): list[tuple[str, str | None, str, str]]
          (list of test definitions)
        - For get_coverage(): float | None (coverage percentage 0-100)
        - For get_coverage_for_tests(): float | None (coverage percentage)
    command : str
        The complete command string that was executed (e.g.,
        "pytest --collect-only -q" or "pytest --cov=myproject").
        This enables reproducibility and audit logging.
    status : int
        The exit status code from the command execution. Zero indicates
        success; non-zero values indicate errors. Follows standard Unix
        convention.
    stdout : str
        Standard output captured from the command execution. Contains the
        normal output text produced by the test suite runner.
    stderr : str
        Standard error captured from the command execution. Contains error
        messages, warnings, and diagnostic information.
    result : object
        Additional framework-specific data or metadata. Can contain:
        - Raw pytest output
        - Parsed JSON coverage reports
        - Framework-specific objects
        - Any supplementary information not captured in other fields

    Notes
    -----
    This class replaces the older tuple-based return format with a more
    explicit and self-documenting structure. It provides better type hints
    and makes code more maintainable by using named fields instead of
    positional tuple elements.

    The dataclass decorator automatically generates __init__, __repr__,
    __eq__, and other useful methods.

    See Also
    --------
    TestSuiteABC : Abstract base class that uses this dataclass.
    PytestSuite : Concrete implementation that returns SuiteRunResult instances.

    """

    value: object
    command: str
    status_code: int
    stdout: str
    stderr: str
    result: object

    @property
    def error(self):
        """Check if the command execution resulted in an error.

        Returns
        -------
        bool
            True if the status_code is non-zero (indicating an error),
            False if the status_code is zero (indicating success).

        """
        return self.status_code > 0

    def raise_if_error(self):
        """Raise an exception if the command execution failed.

        This method checks the error property and raises a
        SuiteRunResultError if the command returned a non-zero exit
        status. This is useful for enforcing error handling in
        test suite operations.

        Raises
        ------
        SuiteRunResultError
            If status_code is non-zero, raises an exception containing
            the status code and stderr output.

        See Also
        --------
        error : Property that checks for error status.
        SuiteRunResultError : The exception raised by this method.
        """
        if self.error:
            raise SuiteRunResultError(self)


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

    def pkg_result(
        self, *, value, command, status_code, stdout, stderr, result
    ):
        """Package test suite execution results into a SuiteRunResult object.

        This helper method creates a standardized SuiteRunResult dataclass
        instance from test suite execution data. It ensures consistent
        return format across all test suite handler methods.

        Parameters
        ----------
        value : object
            The primary result value (tests list or coverage percentage).
        command : str
            The command string that was executed.
        status_code : int
            Exit status code (0 = success, non-zero = error).
        stdout : str
            Standard output captured from command execution.
        stderr : str
            Standard error captured from command execution.
        result : object
            Additional framework-specific data or metadata.

        Returns
        -------
        _SuiteRunResult
            Immutable dataclass containing all execution results and metadata.

        Notes
        -----
        This method should be used by all abstract method implementations
        (get_tests, get_coverage, get_coverage_for_tests) to ensure
        consistent return format for audit logging and result processing.

        See Also
        --------
        _SuiteRunResult : The dataclass returned by this method.
        """
        return _SuiteRunResult(
            value=value,
            command=command,
            status_code=status_code,
            stdout=stdout,
            stderr=stderr,
            result=result,
        )

    # ========================================================================
    # Abstract Methods
    # ========================================================================

    @abstractmethod
    def get_tests(self, project_path) -> _SuiteRunResult:
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
    def get_coverage(self, project_path, project_name) -> _SuiteRunResult:
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
    ) -> _SuiteRunResult:
        """Run specific test(s) with coverage and return coverage percentage.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run coverage on.
        project_name : str
            Name of the project/package to measure coverage for.
        test_ids : list[str]
            List of unique identifiers for tests to run
            (e.g., pytest node IDs). Can be a single-item list for isolated
            test coverage, or multiple items for combined coverage of
            specific tests.

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
        - Multiple tests ([test_id1, test_id2, ...]): Measures combined
          coverage
        - All except one (query result): Enables coverage_without
          calculation

        This flexibility allows for both coverage_alone (single test) and
        coverage_without (all tests except one) metrics.
        """
        pass
