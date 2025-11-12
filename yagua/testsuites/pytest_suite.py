"""
Yagua - Pytest Suite.

This module provides a test suite handler for pytest-based projects.
"""

import re
import subprocess
import sys
from pathlib import Path


# ============================================================================
# PYTEST SUITE
# ============================================================================


class PytestSuite:
    """
    Test suite handler for pytest-based projects.

    This class is responsible for discovering and collecting test information
    from pytest projects using pytest's collection mechanism.
    """

    def _parse_test_line(self, line: str) -> tuple[str, str | None, str] | None:
        """
        Parse a pytest test line into components.

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

    def collect_tests(self, project_path) -> list[tuple[str, str | None, str]]:
        result = subprocess.run(
            ["pytest", "--collect-only", "-q"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=True,
        )

        tests = []
        for line in result.stdout.splitlines():
            parsed = self._parse_test_line(line)
            if parsed:
                tests.append(parsed)

        return tests

    def get_coverage(self, project_path, project_name) -> float | None:
        """
        Run pytest with coverage and return the total coverage percentage.

        Executes pytest with coverage enabled and parses the output to extract
        the total coverage percentage.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run coverage on.

        Returns
        -------
        float | None
            Total coverage percentage (0-100) or None if coverage could not
            be determined.
        """

        result = subprocess.run(
            [
                "pytest",
                "-m=''",
                f"--cov={project_name}",
                f"--cov-report=json:{output}",
            ],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
