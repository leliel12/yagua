"""
Yagua - Pytest Suite.

This module provides a test suite handler for pytest-based projects.
"""

import io
import contextlib
import tempfile
import json

import pytest

from .abc import TestSuiteABC

# ============================================================================
# PYTEST PLUGIN
# ============================================================================


class YaguaPlugin:
    """Pytest plugin for collecting test metadata.

    This plugin hooks into pytest's collection phase to capture additional
    test metadata that can be stored in the yagua database.
    """

    def __init__(self):
        """Initialize the plugin with empty collected items."""
        self.collected_items = []

    def pytest_collection_modifyitems(self, config, items):
        """Called after collection is completed.

        Parameters
        ----------
        config : pytest.Config
            Pytest configuration object.
        items : list[pytest.Item]
            List of collected test items.

        Notes
        -----
        This hook is called after pytest has collected all tests but before
        they are executed. You can modify the items list or extract metadata.

        Examples of what you can extract from each item:
        - item.nodeid: Full test path (e.g., "tests/test_foo.py::TestClass::test_method")
        - item.obj: The actual test function/method object
        - item.keywords: Dictionary of markers and keywords
        - item.callspec: Parametrization info (if test is parametrized)
        """
        # Store collected items for later processing
        self.collected_items = items

        # Access config if needed (currently unused)
        _ = config


# ============================================================================
# PYTEST SUITE
# ============================================================================


class PytestSuite(TestSuiteABC):
    """Test suite handler for pytest-based projects.

    This class implements the TestSuiteABC interface for pytest-based projects,
    providing methods to discover tests and collect coverage information using
    pytest's built-in collection and coverage mechanisms.

    The class uses subprocess calls to pytest CLI commands and returns structured
    data including the executed command, output, and additional metadata for
    audit logging purposes.

    Attributes
    ----------
    _temp_dir : tempfile.TemporaryDirectory
        Temporary directory for storing coverage report files during execution.

    Notes
    -----
    This implementation requires pytest and pytest-cov to be installed in the
    environment where the project tests are being collected.

    Examples
    --------
    >>> suite = PytestSuite()
    >>> tests, cmd, stdout, stderr, data = suite.get_tests("/path/to/project")
    >>> print(f"Found {len(tests)} tests using command: {cmd}")
    >>> coverage, cmd, stdout, stderr, data = suite.get_coverage("/path/to/project", "myproject")
    >>> print(f"Coverage: {coverage}%")
    """

    # ========================================================================
    # Constructor
    # ========================================================================

    def __init__(self):
        """Initialize PytestSuite with temporary directory for coverage files.

        Creates a temporary directory that will be used to store coverage report
        files during coverage collection. The directory is automatically cleaned
        up when the object is destroyed.
        """
        self._temp_dir = tempfile.TemporaryDirectory()

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _run(self, cmd, project_path):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            contextlib.chdir(project_path),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            pytest.main(cmd)

        return " ".join(cmd), stdout.getvalue(), stderr.getvalue()

    def _parse_test_line(
        self, line: str
    ) -> tuple[str, str | None, str] | None:
        """Parse a pytest test line into components.

        Parameters
        ----------
        line : str
            Test line in format 'file::Suite::test' or 'file::test'.

        Returns
        -------
        tuple[str, str | None, str] | None
            Tuple of (file, suite, test) or None if parsing fails.
        """
        line = line.strip()
        parts = line.split("::")
        if len(parts) == 2:
            # Format: file::test
            return (parts[0], None, parts[1])
        elif len(parts) == 3:
            # Format: file::Suite::test
            return (line, parts[0], parts[1], parts[2])

    # ========================================================================
    # Public Methods
    # ========================================================================

    def get_tests(
        self, project_path
    ) -> tuple[list[tuple[str, str | None, str]], str, str, str, str]:
        """Collect all tests from a pytest project.

        Executes pytest with the --collect-only flag to discover all tests
        without running them. Parses the output to extract test information
        in a structured format.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory containing pytest tests.

        Returns
        -------
        tests : list[tuple[str, str | None, str]]
            List of tuples (file, suite, test) for each test found.
            The suite element is None if the test is not part of a test class.
        command : str
            The command that was executed (e.g., "pytest --collect-only -q").
        stdout : str
            Standard output from the pytest command execution.
        stderr : str
            Standard error output from the pytest command execution.
        data : str
            Additional data (same as stdout for consistency with interface).

        Raises
        ------
        subprocess.CalledProcessError
            If pytest command fails or returns non-zero exit code.

        Examples
        --------
        >>> suite = PytestSuite()
        >>> tests, cmd, stdout, stderr, _ = suite.get_tests("/path/to/project")
        >>> for file, suite_name, test in tests:
        ...     print(f"{file}::{suite_name or ''}::{test}")
        """
        command, stdout, stderr = self._run(
            ["--collect-only", "-q"],
            project_path,
        )

        tests = []
        for line in stdout.splitlines():
            parsed = self._parse_test_line(line)
            if parsed:
                tests.append(parsed)

        return tests, command, stdout, stderr, stdout

    def get_coverage(
        self, project_path, project_name
    ) -> tuple[float | None, str, str, str, dict]:
        """Run pytest with coverage and return the total coverage percentage.

        Executes pytest with pytest-cov to run all tests and measure code coverage.
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
        coverage : float | None
            Total coverage percentage (0-100) or None if coverage could not
            be determined.
        command : str
            The command that was executed (e.g., "pytest --cov=package --cov-report=json:...").
        stdout : str
            Standard output from the pytest command execution.
        stderr : str
            Standard error output from the pytest command execution.
        data : dict
            The parsed JSON coverage report containing detailed coverage information.

        Raises
        ------
        subprocess.CalledProcessError
            If pytest command fails or returns non-zero exit code.
        json.JSONDecodeError
            If the coverage JSON report cannot be parsed.

        Notes
        -----
        This method requires pytest-cov to be installed in the environment.
        The coverage report is generated in a temporary file that is automatically
        cleaned up after parsing.

        Examples
        --------
        >>> suite = PytestSuite()
        >>> cov, cmd, stdout, stderr, data = suite.get_coverage("/path/to/project", "mypackage")
        >>> print(f"Total coverage: {cov:.2f}%")
        >>> print(f"Files covered: {len(data.get('files', {}))}")
        """
        with tempfile.NamedTemporaryFile(
            dir=self._temp_dir.name, suffix=".json", prefix="yagua_cov_"
        ) as fp:
            cmd = [
                f"--cov={project_name}",
                f"--cov-report=json:{fp.name}",
            ]
            command, stdout, stderr = self._run(cmd, project_path)
            json_src = fp.read()
            data = json.loads(json_src)

        cov = data["totals"]["percent_covered"]

        return cov, command, stdout, stderr, json_src
