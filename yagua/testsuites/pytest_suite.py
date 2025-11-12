"""
Yagua - Pytest Suite.

This module provides a test suite handler for pytest-based projects.
"""

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
        line = line.strip()
        if not line or "::" not in line:
            return None

        parts = line.split("::")
        if len(parts) == 2:
            # Format: file::test
            return (parts[0], None, parts[1])
        elif len(parts) == 3:
            # Format: file::Suite::test
            return (parts[0], parts[1], parts[2])
        else:
            return None

    def collect_tests(self, project_path) -> list[tuple[str, str | None, str]]:
        """
        Collect all tests from a pytest project.

        Uses pytest's --collect-only flag to discover all tests in the project
        without executing them.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to collect tests from.

        Returns
        -------
        list[tuple[str, str | None, str]]
            List of tuples containing (file, suite, test) where:
            - file: Test file path
            - suite: Test class/suite name (None if test is not in a class)
            - test: Test function name
        """
        try:
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

        except subprocess.CalledProcessError as e:
            print(f"Error running pytest: {e}", file=sys.stderr)
            print(f"stderr: {e.stderr}", file=sys.stderr)
            return []
        except FileNotFoundError:
            print(
                "Error: pytest not found. Please install pytest.", file=sys.stderr
            )
            return []
