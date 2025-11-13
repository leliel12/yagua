"""
Yagua - Pytest Suite.

This module provides a test suite handler for pytest-based projects.
"""

import re
import tempfile
import subprocess
import sys
from pathlib import Path
import json

from .abc import TestSuiteABC


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

    def _run(self, cmd, cwd):
        """Run subprocess command with standard configuration.

        Parameters
        ----------
        cmd : list
            Command and arguments to execute.
        cwd : str or Path
            Working directory for command execution.

        Returns
        -------
        subprocess.CompletedProcess
            Result of the subprocess execution.
        """
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=True
        )
        return " ".join(cmd), result

    def _parse_test_line(self, line: str) -> tuple[str, str | None, str] | None:
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
        parts = line.strip().split("::")
        if len(parts) == 2:
            # Format: file::test
            return (parts[0], None, parts[1])
        elif len(parts) == 3:
            # Format: file::Suite::test
            return (parts[0], parts[1], parts[2])

    # ========================================================================
    # Public Methods
    # ========================================================================

    def get_tests(self, project_path) -> tuple[list[tuple[str, str | None, str]], str, str, str, str]:
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
        command, result = self._run(
            ["pytest", "--collect-only", "-q"],
            cwd=project_path,
        )

        tests = []
        for line in result.stdout.splitlines():
            parsed = self._parse_test_line(line)
            if parsed:
                tests.append(parsed)

        return tests, command, result.stdout, result.stderr, result.stdout

    def get_coverage(self, project_path, project_name) -> tuple[float | None, str, str, str, dict]:
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
            command, result = self._run(
                [
                    "pytest",
                    f"--cov={project_name}",
                    f"--cov-report=json:{fp.name}",
                ],
                cwd=project_path,
            )
            json_src = fp.read()
            data = json.loads(json_src)

        cov = data["totals"]["percent_covered"]

        return cov, command, result.stdout, result.stderr, json_src
