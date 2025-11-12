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


# ============================================================================
# PYTEST SUITE
# ============================================================================


class PytestSuite:
    """
    Test suite handler for pytest-based projects.

    This class is responsible for discovering and collecting test information
    from pytest projects using pytest's collection mechanism.
    """

    def __init__(self):
        """Initialize PytestSuite with temporary directory for coverage files."""
        self._temp_dir = tempfile.TemporaryDirectory()

    # ========================================================================
    # Public Methods
    # ========================================================================

    def get_tests(self, project_path) -> list[tuple[str, str | None, str]]:
        """Collect all tests from a pytest project.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory.

        Returns
        -------
        list[tuple[str, str | None, str]]
            List of tuples (file, suite, test) for each test found.
        """
        result = self._run(
            ["pytest", "--collect-only", "-q"],
            cwd=project_path,
        )

        tests = []
        for line in result.stdout.splitlines():
            parsed = self._parse_test_line(line)
            if parsed:
                tests.append(parsed)

        return tests

    def get_coverage(self, project_path, project_name) -> float | None:
        """Run pytest with coverage and return the total coverage percentage.

        Executes pytest with coverage enabled and parses the JSON output to
        extract the total coverage percentage.

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
        with tempfile.NamedTemporaryFile(
            dir=self._temp_dir.name, suffix=".json", prefix="yagua_cov_"
        ) as fp:
            self._run(
                [
                    "pytest",
                    f"--cov={project_name}",
                    f"--cov-report=json:{fp.name}",
                ],
                cwd=project_path,
            )
            data = json.load(fp)

        cov = data["totals"]["percent_covered"]
        return cov

    # ========================================================================
    # Private Helper Methods
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
        return result

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
