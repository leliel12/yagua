"""Yagua - Collector (Suite Execution Layer).

This module provides the Collector class, which handles test suite and
mutation suite execution. It runs pytest, cosmic-ray, and other testing
frameworks to collect data, but does NOT store it in the database.

The Collector is responsible for:
- Running test suites (pytest, etc.)
- Running mutation suites (cosmic-ray, etc.)
- Collecting coverage information
- Returning collected data to the caller

Data persistence is handled by ProjectStore. Pipeline orchestration
is handled by Project.

Classes
-------
Collector : class
    Suite execution layer that runs testing frameworks and returns data.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from .mutationsuites import CosmicRaySuite
from .testsuites import PytestSuite


# =============================================================================
# CONSTANTS
# =============================================================================

#: Available test suite handlers mapped by name.
TEST_SUITES = {
    "pytest": PytestSuite,
}

#: Available mutation suite handlers mapped by name.
MUTATION_SUITES = {
    "cosmic-ray": CosmicRaySuite,
}


# =============================================================================
# COLLECTOR CLASS
# =============================================================================


class Collector:
    """Suite execution layer for running testing frameworks.

    This class handles the execution of test suites (pytest) and mutation
    suites (cosmic-ray) to collect data. It does NOT store data in the
    database - that responsibility belongs to ProjectStore.

    Parameters
    ----------
    project_path : str or Path
        Path to the project directory being analyzed.
    project_name : str
        Name of the project/package being analyzed.
    work_path : str or Path
        Path to the work directory for temporary files.
    test_suite_name : str
        Name of the test suite to use (e.g., "pytest").
    mutation_suite_name : str
        Name of the mutation suite to use (e.g., "cosmic-ray").
    mutation_timeout : float, optional
        Timeout in seconds for mutation testing. Default is None.

    Attributes
    ----------
    project_path : Path
        Project directory path.
    project_name : str
        Project name.
    work_path : Path
        Work directory path.
    test_suite_name : str
        Test suite name.
    mutation_suite_name : str
        Mutation suite name.
    mutation_timeout : float
        Mutation timeout.
    """

    def __init__(
        self,
        project_path,
        project_name,
        work_path,
        test_suite_name,
        mutation_suite_name,
        mutation_timeout=None,
    ):
        """Initialize Collector with suite configuration.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory being analyzed.
        project_name : str
            Name of the project/package being analyzed.
        work_path : str or Path
            Path to the work directory for temporary files.
        test_suite_name : str
            Name of the test suite to use (e.g., "pytest").
        mutation_suite_name : str
            Name of the mutation suite to use (e.g., "cosmic-ray").
        mutation_timeout : float, optional
            Timeout in seconds for mutation testing. Default is None.
        """
        self.project_path = project_path
        self.project_name = project_name
        self.work_path = work_path
        self.test_suite_name = test_suite_name
        self.mutation_suite_name = mutation_suite_name
        self.mutation_timeout = mutation_timeout

    def _resolve_progress_callbak(self, progress_callback):
        return _no_callback if progress_callback is None else progress_callback

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def test_suite(self):
        """Get test suite handler instance.

        Returns
        -------
        TestSuiteABC
            Instantiated test suite handler.
        """
        suite_cls = TEST_SUITES[self.test_suite_name]
        return suite_cls(self.work_path)

    @property
    def mutation_suite(self):
        """Get mutation testing suite handler instance.

        Returns
        -------
        MutationSuiteABC
            Instantiated mutation suite handler.
        """
        suite_cls = MUTATION_SUITES[self.mutation_suite_name]
        return suite_cls(
            self.work_path,
            mutation_timeout=self.mutation_timeout,
        )

    # ========================================================================
    # Public Methods - Test Collection
    # ========================================================================

    def collect_tests(self):
        """Collect tests from the project using the configured test suite.

        This method runs the test suite's discovery mechanism (e.g.,
        pytest --collect-only) and returns the test data.

        Parameters
        ----------
        progress_callback : callable, optional
            Callback function called for progress updates with signature:
            progress_callback(current, total, test_id).
            Default is None (no-op function).

        Returns
        -------
        dict
            Dictionary with keys:
            - 'tests_data': List of test dictionaries
            - 'result': Suite result object

        Raises
        ------
        ValueError
            If no tests are found in the project.
        """

        suite = self.test_suite
        result = suite.get_tests(self.project_path)
        tests_data = result.value if not result.error else []

        if not tests_data:
            raise ValueError("No tests found in the project.")

        return {"tests_data": tests_data, "result": result}

    # ========================================================================
    # Public Methods - Coverage Collection
    # ========================================================================

    def collect_project_coverage(self):
        """Collect total coverage for all tests combined.

        Returns
        -------
        tuple
            Tuple of (coverage, result) where:
            - coverage: float - Total coverage proportion (0-1)
            - result: SuiteRunResult - Result object from test suite
        """
        suite = self.test_suite

        # Phase 1: Calculate coverage for all tests combined
        result = suite.get_coverage(self.project_path, self.project_name)
        coverage = result.value

        return coverage, result

    def collect_coverage_alone(self, test_id):
        """Collect coverage when running only a single test.

        Parameters
        ----------
        test_id : str
            Unique identifier for the test to run.

        Returns
        -------
        tuple
            Tuple of (coverage, result) where:
            - coverage: float - Coverage proportion (0-1)
            - result: SuiteRunResult - Result object from test suite
        """
        suite = self.test_suite
        result = suite.get_coverage_for_tests(
            self.project_path, self.project_name, [test_id]
        )
        coverage = result.value

        return coverage, result

    def collect_coverage_without(self, test_id, all_test_ids):
        """Collect coverage when running all tests except one.

        Parameters
        ----------
        test_id : str
            Unique identifier for the test to exclude.
        all_test_ids : list[str]
            List of all test IDs in the project.

        Returns
        -------
        tuple
            Tuple of (coverage, result) where:
            - coverage: float - Coverage proportion (0-1)
            - result: SuiteRunResult - Result object from test suite
        """
        suite = self.test_suite
        tids_without = [t for t in all_test_ids if t != test_id]
        result = suite.get_coverage_for_tests(
            self.project_path, self.project_name, tids_without
        )
        coverage = result.value

        return coverage, result

    # ========================================================================
    # Public Methods - Mutation Collection
    # ========================================================================

    def collect_mutants(self, force=False):
        """Initialize mutations and count total mutants.

        Parameters
        ----------
        force : bool, optional
            Force re-initialization even if already done. Default is False.

        Returns
        -------
        tuple
            Tuple of (mutants_number, result) where:
            - mutants_number: int - Total number of mutants generated
            - result: SuiteRunResult - Result object from mutation suite
        """
        suite = self.mutation_suite
        result = suite.get_mutants(
            self.project_path, self.project_name, force=force
        )
        return result.value, result

    def collect_project_msr(self, force=False):
        """Execute mutations and calculate project-wide survival rate.

        Parameters
        ----------
        force : bool, optional
            Force re-execution even if already done. Default is False.

        Returns
        -------
        tuple
            Tuple of (msr, result) where:
            - msr: float - Mutation survival rate (0-1)
            - result: SuiteRunResult - Result object from mutation suite
        """
        suite = self.mutation_suite
        result = suite.get_survival_rate(
            self.project_path, self.project_name, force
        )
        return result.value, result

    def collect_msr_alone(self, test_id, force=False):
        """Collect MSR when running only a single test.

        Parameters
        ----------
        test_id : str
            Unique identifier for the test to run.
        force : bool, optional
            Force re-execution even if already done. Default is False.

        Returns
        -------
        tuple
            Tuple of (msr, result) where:
            - msr: float - Mutation survival rate (0-1)
            - result: SuiteRunResult - Result object from mutation suite
        """
        suite = self.mutation_suite
        result = suite.get_survival_rate_for_tests(
            self.project_path, self.project_name, [test_id], force
        )
        return result.value, result

    def collect_msr_without(self, test_id, all_test_ids, force=False):
        """Collect MSR when running all tests except one.

        Parameters
        ----------
        test_id : str
            Unique identifier for the test to exclude.
        all_test_ids : list[str]
            List of all test IDs in the project.
        force : bool, optional
            Force re-execution even if already done. Default is False.

        Returns
        -------
        tuple
            Tuple of (msr, result) where:
            - msr: float - Mutation survival rate (0-1)
            - result: SuiteRunResult - Result object from mutation suite
        """
        suite = self.mutation_suite
        tids_without = [t for t in all_test_ids if t != test_id]
        result = suite.get_survival_rate_for_tests(
            self.project_path, self.project_name, tids_without, force
        )
        return result.value, result
