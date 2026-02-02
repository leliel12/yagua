"""Yagua - Pytest Suite Handler.

This module provides a test suite handler for pytest-based projects,
implementing the TestSuiteABC interface using subprocess calls to the
pytest CLI and pytest-cov for coverage measurement.

Classes
-------
PytestSuite : class
    Test suite handler for pytest-based projects using system calls.

Implementation Details
----------------------
This implementation uses:
- subprocess.run() for executing pytest as an external command
- --collect-only flag for test discovery
- pytest-cov plugin for coverage measurement
- Hash-based temporary file naming (similar to Cosmic Ray)
- No stdout/stderr redirection (direct subprocess capture)

Key Features
------------
- Non-invasive test discovery (no test execution during collection)
- JSON-based coverage reporting for reliable parsing
- Flexible coverage measurement (total, per-test, and selective)
- Complete audit trail (captures command, stdout, stderr, and results)
- Hash-based temporary files for deterministic file naming

Dependencies
------------
- pytest: Test framework (installed in the target environment)
- pytest-cov: Coverage plugin for pytest
- coverage: Underlying coverage measurement library
"""

import contextlib
import hashlib
import json
import pathlib
import subprocess

from .abc import TestSuiteABC

# ============================================================================
# PYTEST SUITE
# ============================================================================


class PytestSuite(TestSuiteABC):
    """Test suite handler for pytest-based projects.

    This class implements the TestSuiteABC interface for pytest-based projects,
    providing methods to discover tests and collect coverage information by
    executing pytest as an external command via subprocess.

    This implementation invokes pytest as a system command, making it more
    isolated from the current Python environment and potentially more stable
    across different pytest versions.

    Attributes
    ----------
    _work_path : pathlib.Path
        Working directory for storing coverage report files during execution.
        Files are named using hashes for deterministic identification.

    Notes
    -----
    This implementation requires pytest and pytest-cov to be installed in the
    environment where the project tests are being collected. The pytest
    command must be available in the system PATH.
    """

    # ========================================================================
    # Constructor
    # ========================================================================

    def __init__(self, work_path):
        """Initialize PytestSuite with working directory.

        Parameters
        ----------
        work_path : str or Path
            Path to the working directory where intermediate files
            (e.g., coverage reports) will be stored.
        """
        self._verbose = False
        self._work_path = pathlib.Path(work_path) / "yagua_pytest"
        self._work_path.mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _hash_tag(self, tag):
        """Generate MD5 hash from a tag string.

        This method creates a unique hash for a tag, useful for generating
        unique file identifiers when running pytest with different
        configurations.

        Parameters
        ----------
        tag : str
            Tag string to hash.

        Returns
        -------
        str
            Hexadecimal digest of the MD5 hash.

        Notes
        -----
        This is similar to the hash_tests_ids method used in CosmicRaySuite.
        """
        md5 = hashlib.md5(tag.encode("utf8"))
        return md5.hexdigest()

    def _run(self, cmd, project_path):
        """Run pytest command using subprocess.

        This internal method executes pytest as an external command,
        capturing output and changing to the project directory.

        Parameters
        ----------
        cmd : list[str]
            Command arguments to pass to pytest
            (e.g., ['pytest', '--collect-only', '-q']).
        project_path : str or Path
            Working directory for pytest execution. Pytest will run as if
            executed from this directory.

        Returns
        -------
        command : str
            Space-joined command string for audit logging.
        status_code : int
            Exit status code from pytest execution.
        stdout : str
            Captured standard output from pytest execution.
        stderr : str
            Captured standard error from pytest execution.

        Notes
        -----
        This method uses subprocess.run() to execute the command with:
        1. cwd set to the project directory
        2. stdout and stderr captured as text
        3. Shell disabled for security
        """
        full_cmd = " ".join(cmd)
        if self._verbose:
            print(f"[RUN] {project_path} >> {full_cmd!r}")

        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        return (full_cmd, result.returncode, result.stdout, result.stderr)

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

    def _normalize_test_id_paths(self, project_path, tests_ids):
        """Normalize test ID file paths for pytest execution.

        This method converts test IDs that may contain absolute or relative
        file paths into a normalized form that pytest can reliably execute
        from the project directory. It simplifies absolute paths to relative
        filenames when the file exists in the current project directory.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory where pytest will be executed.
        tests_ids : list[str]
            List of test IDs in pytest nodeid format (e.g.,
            'path/to/test_file.py::TestClass::test_method' or
            '/absolute/path/test_file.py::test_function').

        Returns
        -------
        list[str]
            List of normalized test IDs with simplified file paths where
            possible, suitable for passing to pytest command line.

        Notes
        -----
        The normalization process for each test ID:
        1. Parse the test ID into components (file, suite, test)
        2. Convert file path to absolute path
        3. If the file exists in project root with just its basename,
           use the basename; otherwise keep the original path
        4. Reconstruct the test ID from normalized components

        This ensures pytest can find tests whether they were collected
        with absolute paths, relative paths, or just filenames.
        """
        normalized = []
        with contextlib.chdir(project_path):
            # Get the current working directory (project root)
            cwd = pathlib.Path.cwd()

            for test_id in tests_ids:
                # Parse test ID into components: (test_id, file, suite, test)
                # We only need file, suite, and test (skip the full test_id)
                fname, suite, test_name = self._parse_test_line(test_id)[1:]

                # Resolve the file path to absolute form
                fpath = pathlib.Path(fname).resolve()

                # Check if file exists in project root with just its basename
                # If yes, use simple filename; otherwise keep original path
                # This handles cases where tests were collected with absolute
                # paths but can be run with relative paths from project root
                fname = fpath.name if (cwd / fpath.name).is_file() else fname

                # Reconstruct test ID from normalized components
                # Filter out None values
                # (suite can be None for standalone tests)
                parts = fname, suite, test_name
                test_id_normalized = "::".join(
                    p for p in parts if p is not None
                )

                normalized.append(test_id_normalized)

        return normalized

    def _hash_tests_ids(self, tests_ids):
        """Generate MD5 hash from sorted test IDs.

        This method creates a unique hash for a set of test IDs, useful for
        generating unique file identifiers when running coverage with
        specific test subsets.

        Parameters
        ----------
        tests_ids : list[str]
            List of test identifiers to hash.

        Returns
        -------
        str
            Hexadecimal digest of the MD5 hash for the concatenated, sorted
            test IDs.

        Notes
        -----
        Test IDs are sorted before hashing to ensure consistent hashes
        regardless of input order.
        """
        all_ids = "".join(sorted(tests_ids))
        md5 = hashlib.md5(all_ids.encode("utf8"))
        return md5.hexdigest()

    # ========================================================================
    # Public Methods
    # ========================================================================

    def get_tests(self, project_path):
        """Collect all tests from a pytest project.

        Executes pytest with the --collect-only flag to discover all tests
        without running them using subprocess. Parses the output to extract
        test information in a structured format.

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
            ["pytest", "--collect-only", "-q"],
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
        coverage. Uses subprocess to call pytest as an external command.
        Generates a JSON coverage report in a hash-named file and extracts
        the total coverage percentage from it.

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
        The coverage report is generated in a hash-named file in the work
        directory for deterministic identification.
        """
        # Generate hash-based filename for coverage report
        tag = f"get_coverage_{project_name}"
        file_hash = self._hash_tag(tag)
        cov_file = self._work_path / f"cov_{file_hash}.json"

        cmd = [
            "pytest",
            f"--cov={project_name}",
            f"--cov-report=json:{cov_file}",
        ]
        command, status, stdout, stderr = self._run(cmd, project_path)

        # Read and parse the coverage JSON file
        with open(cov_file, "r") as fp:
            json_src = fp.read()
            data = json.loads(json_src)

        cov = data["totals"]["percent_covered"] / 100.0

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
        measure code coverage. Uses subprocess to call pytest as an external
        command. Generates a JSON coverage report in a hash-named file based
        on the test IDs and extracts the total coverage percentage from it.

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

        The coverage report filename is based on a hash of the sorted test
        IDs, ensuring deterministic naming for the same test combinations.
        """
        # Generate hash-based filename for coverage report
        tests_hash = self._hash_tests_ids(tests_ids)
        cov_file = self._work_path / f"ftcov_{tests_hash}.json"

        tests_ids = self._normalize_test_id_paths(project_path, tests_ids)
        cmd = (
            ["pytest"]
            + tests_ids
            + [
                f"--cov={project_name}",
                f"--cov-report=json:{cov_file}",
            ]
        )
        command, status, stdout, stderr = self._run(cmd, project_path)

        # Read and parse the coverage JSON file
        with open(cov_file, "r") as fp:
            json_src = fp.read()
            data = json.loads(json_src)

        cov = data["totals"]["percent_covered"] / 100.0

        return self.pkg_result(
            value=cov,
            command=command,
            status_code=status,
            stdout=stdout,
            stderr=stderr,
            result=json_src,
        )
