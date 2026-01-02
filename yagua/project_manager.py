"""Yagua - Project Manager.

This module provides the ProjectManager class, which encapsulates the
business logic for project operations. It separates the core functionality
from the CLI presentation layer, making the code more maintainable and
testable.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import numpy as np


# =============================================================================
# PRIVATE HELPER FUNCTIONS
# =============================================================================


def _coerce_na(value):
    """
    Coerces input values that are None or NaN (Not a Number) to None.

    This function is useful in data cleaning pipelines where you need a
    consistent representation for missing data points before further processing
    or storage (e.g., storing in a database that uses NULL).

    Parameters
    ----------
    value : Any
        The input value to check. Can be of various types
        (float, int, str, None, etc.).

    Returns
    -------
    Union[Any, None]
        Returns ``None`` if the input value is ``None`` or if it is a
        floating-point ``NaN`` value from numpy. Otherwise, the original value
        is returned unchanged.

    See Also
    --------
    numpy.isnan : Function used internally to check for NaN values.
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return value


# =============================================================================
# PROJECT MANAGER CLASS
# =============================================================================


class ProjectManager:
    """Manages project operations for Yagua.

    This class encapsulates the business logic for project operations,
    separating it from the CLI presentation layer. It handles test
    collection, coverage analysis, mutation testing, and other core
    functionality.

    Parameters
    ----------
    project : Project
        Project instance to manage.

    Attributes
    ----------
    project : Project
        The project instance being managed.

    Methods
    -------
    collect_tests
        Collect tests from a project using pytest.
    get_tests_info
        Get tests information as DataFrame.
    collect_coverage
        Collect and store coverage information.
    collect_mutations
        Collect and analyze mutation testing data.
    get_project_info
        Get project information dictionary.
    export_project
        Export work directory to an archive file.

    Notes
    -----
    This class does not handle any CLI-specific formatting or display.
    All presentation logic should be handled by the CLIManager.
    """

    def __init__(self, project):
        """Initialize ProjectManager with a Project instance.

        Parameters
        ----------
        project : Project
            Project instance to manage.
        """
        self.project = project

    # ========================================================================
    # Public Methods - Test Management
    # ========================================================================

    def collect_tests(self, force=False):
        """Collect tests from the project using pytest.

        This method runs pytest --collect-only to discover all tests
        in the project and stores them in the yagua database.

        Parameters
        ----------
        force : bool
            Force recollection of tests even if already collected.

        Returns
        -------
        dict
            Dictionary with keys:
            - 'total_tests': Total number of tests
            - 'saved_count': Number of new tests saved
            - 'updated_count': Number of existing tests updated
            - 'was_collected': Whether collection was performed

        Raises
        ------
        ValueError
            If no tests are found in the project.
        """
        total_tests = self.project.count_tests()
        saved_count, updated_count = 0, 0
        was_collected = False

        if total_tests == 0 or force:
            saved_count, updated_count = self.project.collect_tests()
            total_tests = saved_count + updated_count
            was_collected = True

        if total_tests == 0:
            raise ValueError("No tests found in the project.")

        return {
            "total_tests": total_tests,
            "saved_count": saved_count,
            "updated_count": updated_count,
            "was_collected": was_collected,
        }

    def get_tests_info(self, include_internal=False):
        """Get tests information as DataFrame.

        Parameters
        ----------
        include_internal : bool, optional
            Include internal columns (id, project, test_id, created_at,
            modified_at). Default is False.

        Returns
        -------
        dict
            Dictionary with keys:
            - 'tests_df': DataFrame with test information
            - 'coverage': Total coverage percentage (or None)
            - 'total_count': Total number of tests

        Raises
        ------
        ValueError
            If no tests are found.
        """
        tests = self.project.get_tests_dataframe()

        # Filter out internal columns unless requested
        if not include_internal:
            ignore_columns = [
                "id",
                "project",
                "test_id",
                "created_at",
                "modified_at",
            ]
            columns = [
                col for col in tests.columns if col not in ignore_columns
            ]
            tests = tests[columns]

        if not len(tests):
            raise ValueError(
                f"No tests found for project: {self.project.name}"
            )

        return {
            "tests_df": tests,
            "coverage": self.project.coverage,
            "total_count": len(tests),
        }

    # ========================================================================
    # Public Methods - Coverage Management
    # ========================================================================

    def collect_coverage(self, force=False, progress_callback=None):
        """Collect and store coverage information for the project.

        This method runs pytest with coverage enabled in three phases:
        1. Total project coverage (all tests)
        2. Per-test coverage (each test in isolation)
        3. Coverage without each test (all tests except one)

        Parameters
        ----------
        force : bool, optional
            Force recalculation of coverage even if it already exists.
            Default is False.
        progress_callback : callable, optional
            Callback function called for each test with signature:
            progress_callback(current, total, test_id).
            Default is None.

        Returns
        -------
        dict
            Dictionary with keys:
            - 'coverage': Total coverage percentage
            - 'tests_data': List of tuples (test_id, cov_alone, cov_wo)

        Raises
        ------
        ValueError
            If no tests found.
        """
        # Validate that there are tests to analyze
        if not self.project.count_tests():
            raise ValueError(
                f"No tests found for project '{self.project.name}'."
            )

        # Phase 1: Calculate coverage for all tests combined
        if self.project.coverage is None or force:
            self.project.collect_coverage()

        coverage = self.project.coverage

        # Phase 2 & 3: Calculate per-test coverage metrics
        tests_ids = self.project.get_tests_dataframe()[
            ["test_id", "coverage_alone", "coverage_without"]
        ].to_numpy()

        tests_count = len(tests_ids)
        tests_data = []

        for idx, (test_id, cov_alone, cov_wo) in enumerate(tests_ids, 1):
            # Call progress callback if provided
            if progress_callback is not None:
                progress_callback(idx, tests_count, test_id)

            # Phase 2: Calculate coverage when running only this test
            cov_alone = _coerce_na(cov_alone)
            if cov_alone is None or force:
                cov_alone = self.project.collect_coverage_for_test(test_id)

            # Phase 3: Calculate coverage when running all tests except
            # this one
            cov_wo = _coerce_na(cov_wo)
            if cov_wo is None or force:
                cov_wo = self.project.collect_coverage_without_test(test_id)

            tests_data.append((test_id, cov_alone, cov_wo))

        return {"coverage": coverage, "tests_data": tests_data}

    # ========================================================================
    # Public Methods - Mutation Management
    # ========================================================================

    def collect_mutations(
        self,
        force=False,
        priority=None,
        ascending=False,
        progress_callback=None,
    ):
        """Collect and analyze mutation testing data for the project.

        This method performs mutation testing analysis in phases:
        1. Mutation initialization (count mutants)
        2. Mutation execution (calculate survival rate)
        3. Per-test mutation analysis

        Parameters
        ----------
        force : bool, optional
            Force recalculation even if mutations exist. Default is False.
        priority : str, optional
            Column to determine test evaluation order. Default is None.
        ascending : bool, optional
            Sort tests in ascending order. Default is False (descending).
        progress_callback : callable, optional
            Callback function called for each test with signature:
            progress_callback(current, total, test_id).
            Default is None.

        Returns
        -------
        dict
            Dictionary with keys:
            - 'mutants_number': Total number of mutants
            - 'msr': Mutation survival rate percentage
            - 'tests_data': List of tuples (test_id, msr_alone, msr_wo)

        Raises
        ------
        ValueError
            If coverage data does not exist or is incomplete.
        """
        # Validate that coverage exists before running mutations
        if not self.project.coverage:
            raise ValueError(
                "Coverage data is required before running mutation analysis."
            )

        # Phase 1: Initialize mutations and count mutants
        if self.project.mutants_number is None or force:
            self.project.collect_mutants(force=force)

        mutants_number = self.project.mutants_number

        # Phase 2: Execute mutations and calculate survival rate
        if self.project.msr is None or force:
            self.project.collect_survival_rate(force)

        msr = self.project.msr

        # Prepare dataframe with mutation and coverage columns
        if priority is None:
            priority = "coverage_uniqueness"

        cov_columns = list({"coverage_alone", "coverage_without", priority})
        mutation_columns = ["test_id", "msr_alone", "msr_without"]

        tests_df = self.project.get_tests_dataframe()[
            mutation_columns + cov_columns
        ]
        tests_df.sort_values(priority, ascending=ascending, inplace=True)

        # Validate that coverage collection is complete
        if tests_df[cov_columns].isna().to_numpy().any():
            raise ValueError(
                "Coverage collection appears to be incomplete. "
                "Some tests are missing coverage data."
            )

        # Phase 3: Calculate per-test mutation metrics
        tests_data_arr = tests_df[mutation_columns].to_numpy()
        tests_count = len(tests_data_arr)

        tests_data = []
        for idx, (test_id, msr_alone, msr_wo) in enumerate(tests_data_arr, 1):
            # Call progress callback if provided
            if progress_callback is not None:
                progress_callback(idx, tests_count, test_id)

            # Phase 2: Calculate mutation score when running only this test
            msr_alone = _coerce_na(msr_alone)
            if msr_alone is None or force:
                msr_alone = self.project.collect_survival_rate_for_test(
                    test_id, force=force
                )

            # Phase 3: Calculate mutation score when running all tests
            # except this one
            msr_wo = _coerce_na(msr_wo)
            if msr_wo is None or force:
                msr_wo = self.project.collect_survival_rate_without_test(
                    test_id, force=force
                )

            tests_data.append((test_id, msr_alone, msr_wo))

        return {
            "mutants_number": mutants_number,
            "msr": msr,
            "tests_data": tests_data,
        }

    # ========================================================================
    # Public Methods - Project Information
    # ========================================================================

    def get_project_info(self):
        """Get project information dictionary.

        Returns
        -------
        dict
            Dictionary with project information including:
            - 'name': Project name
            - 'path': Project path
            - 'work_dir': Work directory path
            - 'db_path': Database path
            - 'description': Project description (or None)
            - 'test_count': Number of tests
            - 'coverage': Coverage percentage (or None)
            - 'mutants_number': Number of mutants (or None)
        """
        test_count = self.project.count_tests()

        return {
            "name": self.project.name,
            "path": self.project.path,
            "work_dir": self.project.work_dir,
            "db_path": self.project.db_path,
            "description": self.project.description,
            "test_count": test_count,
            "coverage": self.project.coverage,
            "mutants_number": self.project.mutants_number,
        }

    def export_project(self, output_path):
        """Export work directory to an archive file.

        This method creates an archive file containing the entire work
        directory, including the yagua.db database and all temporary files.

        Parameters
        ----------
        output_path : Path, optional
            Output path including the desired extension. If not provided,
            defaults to '<work_dir_name>.zip' in the current directory.

        Returns
        -------
        Path
            Path to the created archive file.

        Raises
        ------
        Exception
            If export fails.
        """
        archive_path = self.project.export(output_path=output_path)
        return archive_path
