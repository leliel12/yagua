"""Yagua - Pytest Suite Handler.

This module provides a test suite handler for pytest-based projects,
implementing the TestSuiteABC interface using pytest's built-in APIs
and pytest-cov for coverage measurement.

Classes
-------
IgnoreTest : class
    Pytest plugin for test collection hooks (currently minimal implementation).
PytestSuite : class
    Main test suite handler for pytest-based projects.

Implementation Details
----------------------
This implementation uses:
- pytest.main() API for running pytest programmatically
- --collect-only flag for test discovery
- pytest-cov plugin for coverage measurement
- Temporary files for coverage JSON reports
- Context managers for stdout/stderr redirection

Key Features
------------
- Non-invasive test discovery (no test execution during collection)
- JSON-based coverage reporting for reliable parsing
- Flexible coverage measurement (total, per-test, and selective)
- Complete audit trail (captures command, stdout, stderr, and results)

Dependencies
------------
- pytest: Test framework
- pytest-cov: Coverage plugin for pytest
- coverage: Underlying coverage measurement library
"""

import io
import contextlib
import tempfile
import json

import pytest

from .abc import TestSuiteABC

# ============================================================================
# PYTEST SUITE
# ============================================================================


class PytestSuite(TestSuiteABC):
    """Test suite handler for pytest-based projects.

    This class implements the TestSuiteABC interface for pytest-based projects,
    providing methods to discover tests and collect coverage information using
    pytest's built-in collection and coverage mechanisms.

    The class uses subprocess calls to pytest CLI commands and returns
    structured data including the executed command, output, and additional
    metadata for audit logging purposes.

    Attributes
    ----------
    _temp_dir : tempfile.TemporaryDirectory
        Temporary directory for storing coverage report files during execution.

    Notes
    -----
    This implementation requires pytest and pytest-cov to be installed in the
    environment where the project tests are being collected.
    """

    # ========================================================================
    # Constructor
    # ========================================================================

    def __init__(self):
        """Initialize PytestSuite with temporary directory for coverage files.

        Creates a temporary directory that will be used to store coverage
        report files during coverage collection. The directory is
        automatically cleaned
        up when the object is destroyed.
        """
        self._temp_dir = tempfile.TemporaryDirectory()

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _run(self, cmd, project_path, plugins=None):
        """Run pytest command using pytest.main() API.

        This internal method executes pytest programmatically, redirecting
        output to string buffers and changing to the project directory.

        Parameters
        ----------
        cmd : list[str]
            Command arguments to pass to pytest.main()
            (e.g., ['--collect-only', '-q']).
        project_path : str or Path
            Working directory for pytest execution. Pytest will run as if
            executed from this directory.
        plugins : list, optional
            List of plugin instances to register with pytest. Default is None.

        Returns
        -------
        command : str
            Space-joined command string for audit logging.
        stdout : str
            Captured standard output from pytest execution.
        stderr : str
            Captured standard error from pytest execution.

        Notes
        -----
        This method uses context managers to:
        1. Change to the project directory (contextlib.chdir)
        2. Redirect stdout to a StringIO buffer
        3. Redirect stderr to a StringIO buffer

        All context changes are automatically reverted when the method returns.
        """
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            contextlib.chdir(project_path),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            status = pytest.main(cmd, plugins=plugins)

        return (
            " ".join(cmd),
            status,
            stdout.getvalue(),
            stderr.getvalue(),
        )

    def _parse_test_line(
        self, line: str
    ) -> tuple[str, str, str | None, str] | None:
        """Parse a pytest test line into components.

        This method parses pytest nodeid strings into their component parts,
        handling both standalone test functions and class-based tests.

        Parameters
        ----------
        line : str
            Test line in pytest nodeid format:
            - 'file.py::test_function' for standalone tests
            - 'file.py::TestClass::test_method' for class-based tests

        Returns
        -------
        tuple[str, str, str | None, str] | None
            Parsed test components as (test_id, file, suite, test), or None
            if the line doesn't match expected formats:
            - test_id: Full pytest nodeid (the complete input line)
            - file: Test file path (e.g., 'test_foo.py')
            - suite: Test suite/class name (e.g., 'TestFoo'), or None
            - test: Test function name (e.g., 'test_bar')

        Notes
        -----
        This parser handles the two most common pytest nodeid formats:
        - 2 parts (file::test): Standalone test functions
        - 3 parts (file::class::test): Class-based test methods

        Lines with other formats (e.g., 1 part, 4+ parts) return None.
        """
        line = line.strip()
        parts = line.split("::")
        if len(parts) == 2:
            # Format: file::test (standalone function)
            return (line, parts[0], None, parts[1])
        elif len(parts) == 3:
            # Format: file::Suite::test (class-based test)
            return (line, parts[0], parts[1], parts[2])
        # Return None for unexpected formats
        return None

    # ========================================================================
    # Public Methods
    # ========================================================================

    def get_tests(self, project_path):
        """Collect all tests from a pytest project.

        Executes pytest with the --collect-only flag to discover all tests
        without running them using pytest.main() API. Parses the output to
        extract test information in a structured format.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory containing pytest tests.

        Returns
        -------
        SuiteRunResult
            Result containing:
            - value: list[tuple[str, str, str | None, str]] - List of tuples
              (test_id, file, suite, test) for each test found
            - command: str - The pytest command arguments executed
            - status_code: int - Exit status from pytest
            - stdout: str - Standard output from pytest
            - stderr: str - Standard error from pytest
            - result: str - Additional data (stdout copy)
        """
        command, status, stdout, stderr = self._run(
            ["--collect-only", "-q"],
            project_path,
        )

        tests = []
        for line in stdout.splitlines():
            parsed = self._parse_test_line(line)
            if parsed:
                tests.append(parsed)

        return self.pkg_result(
            value=tests,
            command=command,
            status_code=status,
            stdout=stdout,
            stderr=stderr,
            result=stdout,
        )

    def get_coverage(self, project_path, project_name):
        """Run pytest with coverage and return the total coverage percentage.

        Executes pytest with pytest-cov to run all tests and measure code
        coverage. Uses pytest.main() API for better integration.
        Generates a JSON coverage report in a temporary file and extracts the
        total coverage percentage from it.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run coverage on.
        project_name : str
            Name of the project/package to measure coverage for.
            This should match the package name in the project.

        Returns
        -------
        SuiteRunResult
            Result containing:
            - value: float | None - Total coverage percentage (0-100)
            - command: str - The pytest command executed
            - status_code: int - Exit status from pytest
            - stdout: str - Standard output from pytest
            - stderr: str - Standard error from pytest
            - result: str - Raw JSON coverage report

        Raises
        ------
        json.JSONDecodeError
            If the coverage JSON report cannot be parsed.

        Notes
        -----
        This method requires pytest-cov to be installed in the environment.
        The coverage report is generated in a temporary file that is
        automatically cleaned up after parsing.
        """
        with tempfile.NamedTemporaryFile(
            dir=self._temp_dir.name,
            suffix=".json",
            prefix="yagua_cov_",
        ) as fp:
            cmd = [
                f"--cov={project_name}",
                f"--cov-report=json:{fp.name}",
            ]
            command, status, stdout, stderr = self._run(cmd, project_path)
            json_src = fp.read()
            data = json.loads(json_src)

        cov = data["totals"]["percent_covered"]

        return self.pkg_result(
            value=cov,
            command=command,
            status_code=status,
            stdout=stdout,
            stderr=stderr,
            result=json_src,
        )

    def get_coverage_for_tests(self, project_path, project_name, tests_ids):
        """Run specific test(s) with coverage and return coverage percentage.

        Executes pytest with pytest-cov to run only the specified tests and
        measure code coverage. Uses pytest.main() API for better integration.
        Generates a JSON coverage report in a temporary file and extracts the
        total coverage percentage from it.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run coverage on.
        project_name : str
            Name of the project/package to measure coverage for.
            This should match the package name in the project.
        tests_ids : list[str]
            List of unique identifiers for tests to run
            (e.g., pytest node IDs). Can be a single-item list for isolated
            test coverage, or multiple items for combined coverage of
            specific tests.

        Returns
        -------
        SuiteRunResult
            Result containing:
            - value: float | None - Coverage percentage (0-100) for the
              specified test(s)
            - command: str - The pytest command executed
            - status_code: int - Exit status from pytest
            - stdout: str - Standard output from pytest
            - stderr: str - Standard error from pytest
            - result: str - Raw JSON coverage report

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
        with tempfile.NamedTemporaryFile(
            dir=self._temp_dir.name,
            suffix=".json",
            prefix="yagua_ftcov_",
        ) as fp:
            cmd = list(tests_ids) + [
                f"--cov={project_name}",
                f"--cov-report=json:{fp.name}",
            ]
            command, status, stdout, stderr = self._run(cmd, project_path)

            json_src = fp.read()
            data = json.loads(json_src)

        cov = data["totals"]["percent_covered"]

        return self.pkg_result(
            value=cov,
            command=command,
            status_code=status,
            stdout=stdout,
            stderr=stderr,
            result=json_src,
        )
