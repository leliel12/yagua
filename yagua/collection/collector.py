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
# PRIVATE HELPER FUNCTIONS
# =============================================================================


def _default_callback(current, total, test_id):
    pass


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
        self.work_path = work_path
        self.test_suite_name = test_suite_name
        self.mutation_suite_name = mutation_suite_name
        self.mutation_timeout = mutation_timeout

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

    def collect_tests(self, progress_callback=_default_callback):
        """Collect tests from the project using the configured test suite.

        This method runs the test suite's discovery mechanism (e.g.,
        pytest --collect-only) and returns the test data.

        Parameters
        ----------
        progress_callback : callable, optional
            Callback function called for progress updates with signature:
            progress_callback(current, total, test_id).
            Default is _default_callback (no-op function).

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
        progress_callback(0, 1, "collecting")

        suite = self.test_suite
        result = suite.get_tests(self.project_path)
        tests_data = result.value if not result.error else []

        progress_callback(1, 1, "collecting")

        if not tests_data:
            raise ValueError("No tests found in the project.")

        return {"tests_data": tests_data, "result": result}

    # ========================================================================
    # Public Methods - Coverage Collection
    # ========================================================================

    def collect_coverage(
        self, project_name, test_ids, progress_callback=_default_callback
    ):
        """Collect coverage information for the project.

        This method runs the test suite with coverage enabled in phases:
        1. Total project coverage (all tests)
        2. Per-test coverage (each test in isolation)
        3. Coverage without each test (all tests except one)

        Parameters
        ----------
        project_name : str
            Project name for reporting.
        test_ids : list of str
            List of test IDs to analyze.
        progress_callback : callable, optional
            Callback function called for each test with signature:
            progress_callback(current, total, test_id).
            Default is _default_callback (no-op function).

        Returns
        -------
        dict
            Dictionary with keys:
            - 'total_coverage': Total coverage percentage
            - 'total_result': Suite result for total coverage
            - 'per_test_data': List of dicts with test coverage data

        Raises
        ------
        ValueError
            If no tests found.
        """
        suite = self.test_suite

        # Phase 1: Calculate coverage for all tests combined
        progress_callback(0, len(test_ids) + 1, "All Tests")
        total_result = suite.get_coverage(self.project_path, project_name)
        total_coverage = total_result.value

        # Phase 2 & 3: Calculate per-test coverage metrics
        per_test_data = []
        for idx, test_id in enumerate(test_ids, 1):
            progress_callback(idx, len(test_ids) + 1, test_id)

            # Phase 2: Coverage when running only this test
            result_alone = suite.get_coverage_for_tests(
                self.project_path, project_name, [test_id]
            )
            cov_alone = result_alone.value

            # Phase 3: Coverage when running all tests except this one
            tids_without = [t for t in test_ids if t != test_id]
            result_without = suite.get_coverage_for_tests(
                self.project_path, project_name, tids_without
            )
            cov_without = result_without.value

            per_test_data.append(
                {
                    "test_id": test_id,
                    "coverage_alone": cov_alone,
                    "coverage_without": cov_without,
                    "result_alone": result_alone,
                    "result_without": result_without,
                }
            )

        return {
            "total_coverage": total_coverage,
            "total_result": total_result,
            "per_test_data": per_test_data,
        }

    # ========================================================================
    # Public Methods - Mutation Collection
    # ========================================================================

    def collect_mutations(
        self,
        project_name,
        test_ids,
        force=False,
        progress_callback=_default_callback,
    ):
        """Collect mutation testing data for the project.

        This method performs mutation testing analysis in phases:
        1. Mutation initialization (count mutants)
        2. Mutation execution (calculate survival rate)
        3. Per-test mutation analysis (msr_alone and msr_without)

        Parameters
        ----------
        project_name : str
            Project name for reporting.
        test_ids : list of str
            List of test IDs to analyze (ordered by priority).
        force : bool, optional
            Force re-execution of mutations even if already run.
            Default is False.
        progress_callback : callable, optional
            Callback function with signature:
            progress_callback(current, total, test_id).
            Default is _default_callback (no-op function).

        Returns
        -------
        dict
            Dictionary with keys:
            - 'mutants_number': Number of mutants generated
            - 'mutants_result': SuiteRunResult for initialization
            - 'msr': Mutation survival rate percentage
            - 'msr_result': SuiteRunResult for execution
            - 'per_test_data': List of dicts with test mutation data
        """
        suite = self.mutation_suite

        # Phase 1: Initialize mutations and count mutants
        progress_callback(0, len(test_ids) + 1, "Initializing")
        mutants_result = suite.get_mutants(
            self.project_path, project_name, force=force
        )

        # Phase 2: Execute mutations and calculate survival rate
        progress_callback(0, len(test_ids) + 1, "All tests")
        msr_result = suite.get_survival_rate(
            self.project_path, project_name, force
        )

        # Phase 3: Per-test mutation analysis
        per_test_data = []
        for idx, test_id in enumerate(test_ids, 1):
            progress_callback(idx, len(test_ids) + 1, test_id)

            # MSR when running only this test
            result_alone = suite.get_survival_rate_for_tests(
                self.project_path, project_name, [test_id], force
            )

            # MSR when running all tests except this one
            tids_without = [t for t in test_ids if t != test_id]
            result_without = suite.get_survival_rate_for_tests(
                self.project_path, project_name, tids_without, force
            )

            per_test_data.append(
                {
                    "test_id": test_id,
                    "msr_alone": result_alone.value,
                    "result_alone": result_alone,
                    "msr_without": result_without.value,
                    "result_without": result_without,
                }
            )

        return {
            "mutants_number": mutants_result.value,
            "mutants_result": mutants_result,
            "msr": msr_result.value,
            "msr_result": msr_result,
            "per_test_data": per_test_data,
        }
