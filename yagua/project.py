"""Yagua - Project Class (Business Logic Layer).

This module provides the Project class, which orchestrates the
pipeline workflow by coordinating the Collector (suite execution) and
ProjectStore (data persistence).

The Project implements a pipeline workflow:
1. created -> Project is initialized
2. tests_collected -> Tests have been collected
3. coverage_collected -> Coverage has been analyzed
4. mutations_collected -> Mutations have been analyzed
5. completed -> All analysis steps finished

Classes
-------
Project : class
    Orchestration layer that coordinates Collector and Store.

Functions
---------
from_work_dir : function
    Factory function to create Project from existing work directory.
from_project_info : function
    Factory function to create new Project with configuration.
"""

# =============================================================================
# IMPORTS
# =============================================================================

from datetime import datetime, timezone

from .collection import Collector
from .dal import ProjectStore
from .utils.bunch import Bunch


# =============================================================================
# CONSTANTS
# =============================================================================

#: Valid pipeline steps in order
PIPELINE_STEPS = [
    "created",
    "tests_collected",
    "coverage_collected",
    "mutations_collected",
]

#: Mapping of pipeline steps to their index for ordering
PIPELINE_ORDER = {step: idx for idx, step in enumerate(PIPELINE_STEPS)}


# =============================================================================
# EXCEPTIONS
# =============================================================================


class PipelineError(Exception):
    """Exception raised when pipeline step validation fails."""

    pass


# =============================================================================
# PROJECT CLASS
# =============================================================================


class Project:
    """Orchestration layer for Yagua project pipeline.

    This class orchestrates the project pipeline by coordinating the
    Collector (suite execution) and ProjectStore (data persistence).
    It validates pipeline steps, manages state transitions, and handles
    the complete workflow from test collection to mutation analysis.

    Parameters
    ----------
    store : ProjectStore
        ProjectStore instance (DAL) for database operations.
    collector : Collector
        Collector instance for suite execution.

    Attributes
    ----------
    store : ProjectStore
        The project DAL instance.
    collector : Collector
        The collector instance for running suites.

    Notes
    -----
    This class does not handle any CLI-specific formatting or display.
    All presentation logic should be handled by the CLI layer.
    """

    def __init__(self, store, collector):
        """Initialize Project with store and collector.

        Parameters
        ----------
        store : ProjectStore
            ProjectStore instance to manage.
        collector : Collector
            Collector instance for suite execution.
        """
        self.store = store
        self.collector = collector

    # ========================================================================
    # Private Methods - Pipeline Management
    # ========================================================================

    def _get_current_step(self):
        """Get current pipeline step from the database.

        Returns
        -------
        str
            Current pipeline step.
        """
        return self.store.pipeline_step

    def _validate_step(self, required_step):
        """Validate that the required pipeline step has been completed.

        Parameters
        ----------
        required_step : str
            The pipeline step that must have been completed.

        Raises
        ------
        PipelineError
            If the required step has not been completed yet.
        """
        current = self._get_current_step()
        current_idx = PIPELINE_ORDER.get(current, -1)
        required_idx = PIPELINE_ORDER.get(required_step, -1)

        if current_idx < required_idx:
            raise PipelineError(
                f"Cannot proceed: required pipeline step '{required_step}' "
                f"has not been completed yet. Current step: '{current}'."
            )

    def _update_step(self, new_step):
        """Update the pipeline step in the database.

        Parameters
        ----------
        new_step : str
            New pipeline step to set.

        Raises
        ------
        ValueError
            If the new step is not valid or out of order.
        """
        if new_step not in PIPELINE_ORDER:
            raise ValueError(
                f"Invalid pipeline step: {new_step}. "
                f"Valid steps: {', '.join(PIPELINE_STEPS)}"
            )

        current = self._get_current_step()
        current_idx = PIPELINE_ORDER[current]
        new_idx = PIPELINE_ORDER[new_step]

        # Allow moving to the next step or staying in the same step
        if new_idx < current_idx:
            raise ValueError(
                f"Cannot move backwards in pipeline from '{current}' "
                f"to '{new_step}'"
            )

        # Delegate to ProjectStore for the database update
        self.store.update_pipeline_step(new_step)

    def next_step(self):
        """Get the next method to execute in the pipeline based on \
        current state.

        Returns
        -------
        callable | None
            Next method to execute (collect_tests, collect_coverage,
            collect_mutations), or None if pipeline is complete.

        Notes
        -----
        This method determines the next step by examining the current
        pipeline_step value:
        - 'created' -> collect_tests
        - 'tests_collected' -> collect_coverage
        - 'coverage_collected' -> collect_mutations
        - 'mutations_collected' -> None (pipeline complete)
        """
        current = self._get_current_step()

        if current == "created":
            return self.collect_tests
        elif current == "tests_collected":
            return self.collect_coverage
        elif current == "coverage_collected":
            return self.collect_mutations
        return None

    # ========================================================================
    # Public Methods - Test Collection
    # ========================================================================

    def collect_tests(self, force=False, progress_callback=None):
        """Collect tests from the project using the configured test suite.

        This method runs the test suite's discovery mechanism and stores
        the results in the database.

        Pipeline step: Updates from 'created' to 'tests_collected'.

        Parameters
        ----------
        force : bool, optional
            Force recollection of tests even if already collected.
            Default is False.
        progress_callback : callable, optional
            Callback function called for progress updates with signature:
            progress_callback(current, total, test_id).
            Default is _default_callback (no-op function).

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
        PipelineError
            If called before project is created.
        """
        # Validate pipeline: must be at least 'created'
        self._validate_step("created")

        total_tests = self.store.count_tests()
        saved_count, updated_count = 0, 0
        was_collected = False

        if total_tests == 0 or force:
            # Use collector to gather test data
            collected = self.collector.collect_tests(progress_callback)
            tests_data = collected["tests_data"]
            result = collected["result"]

            # Save to database via store
            saved_count, updated_count = self.store.save_tests(
                tests_data=tests_data, result=result
            )
            total_tests = saved_count + updated_count
            was_collected = True

        if total_tests == 0:
            raise ValueError("No tests found in the project.")

        # Update pipeline step
        self._update_step("tests_collected")

        return {
            "total_tests": total_tests,
            "saved_count": saved_count,
            "updated_count": updated_count,
            "was_collected": was_collected,
        }

    # ========================================================================
    # Public Methods - Coverage Collection
    # ========================================================================

    def collect_coverage(
        self, force=False, progress_callback=None
    ):
        """Collect and store coverage information for the project.

        This method coordinates coverage collection through the collector
        and persists results via the store.

        Pipeline step: Updates from 'tests_collected' to
        'coverage_collected'.

        Parameters
        ----------
        force : bool, optional
            Force recalculation of coverage even if it already exists.
            Default is False.
        progress_callback : callable, optional
            Callback function called for each test with signature:
            progress_callback(current, total, test_id).
            Default is _default_callback (no-op function).

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
        PipelineError
            If called before tests are collected.
        """
        # Validate pipeline: must have collected tests
        self._validate_step("tests_collected")

        # Validate that there are tests to analyze
        if not self.store.count_tests():
            raise ValueError(
                f"No tests found for project '{self.store.name}'."
            )

        # Phase 1: Calculate coverage for all tests combined
        if self.store.coverage is None or force:
            progress_callback(0, 1, "All Tests")

            # Get all test IDs from dataframe
            test_ids = self.store.get_tests_dataframe()["test_id"].tolist()

            # Collect coverage using collector
            collected = self.collector.collect_coverage(
                test_ids, progress_callback
            )

            # Save total coverage
            self.store.save_coverage(
                value=collected["total_coverage"],
                result=collected["total_result"],
            )

            # Save per-test coverage
            for test_data in collected["per_test_data"]:
                test_id = test_data["test_id"]

                self.store.save_test_coverage_alone(
                    test_id=test_id,
                    value=test_data["coverage_alone"],
                    result=test_data["result_alone"],
                )

                self.store.save_test_coverage_without(
                    test_id=test_id,
                    value=test_data["coverage_without"],
                    result=test_data["result_without"],
                )

        coverage = self.store.coverage

        # Get final coverage data
        tests_data = []
        tests_df = self.store.get_tests_dataframe()[
            ["test_id", "coverage_alone", "coverage_without"]
        ]

        for _, row in tests_df.iterrows():
            tests_data.append(
                (
                    row["test_id"],
                    row["coverage_alone"],
                    row["coverage_without"],
                )
            )

        # Update pipeline step
        self._update_step("coverage_collected")

        return {"coverage": coverage, "tests_data": tests_data}

    # ========================================================================
    # Public Methods - Mutation Collection
    # ========================================================================

    def collect_mutations(
        self, force=False, progress_callback=None
    ):
        """Collect and analyze mutation testing data for the project.

        This method coordinates mutation testing through the mutation
        suite and persists results via the store.

        Pipeline step: Updates from 'coverage_collected' to
        'mutations_collected'.

        Parameters
        ----------
        force : bool, optional
            Force recalculation even if mutations exist. Default is False.
        progress_callback : callable, optional
            Callback function called for each test with signature:
            progress_callback(current, total, test_id).
            Default is _default_callback (no-op function).

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
        PipelineError
            If called before coverage is collected.
        """
        # Validate pipeline: must have collected coverage
        self._validate_step("coverage_collected")

        # Validate that coverage exists before running mutations
        if not self.store.coverage:
            raise ValueError(
                "Coverage data is required before running "
                "mutation analysis."
            )

        if self.store.mutants_number is None or force:
            # Get tests ordered by priority (coverage_alone)
            priority = "coverage_alone"
            cov_columns = list({"coverage_alone", "coverage_without"})
            tests_df = self.store.get_tests_dataframe()[
                ["test_id"] + cov_columns
            ]
            tests_df.sort_values(priority, ascending=False, inplace=True)

            # Validate that coverage collection is complete
            if tests_df[cov_columns].isna().to_numpy().any():
                raise ValueError(
                    "Coverage collection appears to be incomplete. "
                    "Some tests are missing coverage data."
                )

            test_ids = tests_df["test_id"].tolist()

            # Collect mutations using collector
            collected = self.collector.collect_mutations(
                test_ids, force, progress_callback
            )

            # Save mutants number
            self.store.save_mutants_number(
                value=collected["mutants_number"],
                result=collected["mutants_result"],
            )

            # Save overall MSR
            self.store.save_msr(
                value=collected["msr"],
                result=collected["msr_result"],
            )

            # Save per-test mutation data
            for test_data in collected["per_test_data"]:
                test_id = test_data["test_id"]

                self.store.save_test_msr_alone(
                    test_id=test_id,
                    value=test_data["msr_alone"],
                    result=test_data["result_alone"],
                )

                self.store.save_test_msr_without(
                    test_id=test_id,
                    value=test_data["msr_without"],
                    result=test_data["result_without"],
                )

        mutants_number = self.store.mutants_number
        msr = self.store.msr

        # Get final mutation data
        tests_data = []
        mutation_df = self.store.get_tests_dataframe()[
            ["test_id", "msr_alone", "msr_without"]
        ]
        for _, row in mutation_df.iterrows():
            tests_data.append(
                (row["test_id"], row["msr_alone"], row["msr_without"])
            )

        # Update pipeline step
        self._update_step("mutations_collected")

        return {
            "mutants_number": mutants_number,
            "msr": msr,
            "tests_data": tests_data,
        }

    # ========================================================================
    # Public Methods - Information and Status
    # ========================================================================

    def get_tests_report(self, include_internal=False):
        """Get tests information as DataFrame.

        Pipeline step: Requires 'tests_collected' or later.

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
        PipelineError
            If called before tests are collected.
        """
        # Validate pipeline: must have collected tests
        self._validate_step("tests_collected")

        tests = self.store.get_tests_dataframe()

        if tests.empty:
            raise ValueError("No tests found in the project.")

        # Drop internal columns if requested
        if not include_internal:
            internal_cols = [
                "id",
                "project",
                "test_id",
                "created_at",
                "modified_at",
            ]
            tests = tests.drop(
                columns=[c for c in internal_cols if c in tests.columns]
            )

        the_report = {
            "tests_df": tests,
            "tests_number": len(tests),
            "coverage": self.store.coverage,
            "mutants_number": self.store.mutants_number,
            "msr": self.store.msr,
            "mutants_killed": self.store.mutants_killed,
            "mutants_survived": self.store.mutants_survived,
            "mutation_active_test_ratio": self.store.mutation_active_test_ratio,
            "macrostate_tightness_ratio": self.store.macrostate_tightness_ratio,
        }

        return Bunch("report", the_report)

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
        test_count = self.store.count_tests()

        return {
            "name": self.store.name,
            "path": self.store.path,
            "work_dir": self.store.work_dir,
            "db_path": self.store.db_path,
            "description": self.store.description,
            "test_count": test_count,
            "coverage": self.store.coverage,
            "mutants_number": self.store.mutants_number,
        }

    def get_pipeline_status(self):
        """Get current pipeline status.

        Returns
        -------
        dict
            Dictionary with keys:
            - 'current_step': Current pipeline step
            - 'tests_collected': Boolean
            - 'coverage_collected': Boolean
            - 'mutations_collected': Boolean
        """
        current = self._get_current_step()
        current_idx = PIPELINE_ORDER[current]

        return {
            "current_step": current,
            "tests_collected": current_idx
            >= PIPELINE_ORDER["tests_collected"],
            "coverage_collected": current_idx
            >= PIPELINE_ORDER["coverage_collected"],
            "mutations_collected": current_idx
            >= PIPELINE_ORDER["mutations_collected"],
        }

    def mark_failed(self):
        """Mark the project as failed with current timestamp.

        This method updates the project's failed_at timestamp to indicate
        when a pipeline failure occurred.
        """
        with self.store.transaction():
            proj_model = self.store._get_project_model()
            proj_model.failed_at = datetime.now(timezone.utc)
            proj_model.save()

    def export_project(self, output_path):
        """Export work directory to an archive file.

        This method creates an archive file containing the entire work
        directory, including the yagua.db database and all temporary
        files.

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
        archive_path = self.store.export(output_path=output_path)
        return archive_path


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def from_work_dir(work_dir):
    """Create Project from existing work directory.

    This factory function reads the project configuration from the
    database and creates the Store, Collector, and Project instances.

    Parameters
    ----------
    work_dir : str or Path
        Path to existing work directory containing yagua.db.

    Returns
    -------
    Project
        Configured Project instance ready to run pipeline.

    Raises
    ------
    FileNotFoundError
        If work directory or database does not exist.

    Examples
    --------
    >>> proj = from_work_dir("/path/to/work_dir")
    >>> proj.collect_tests()
    >>> proj.collect_coverage()
    """
    # Create ProjectStore (DAL)
    store = ProjectStore(work_dir)

    # Create Collector (suite execution)
    collector = Collector(
        project_path=store.path,
        project_name=store.name,
        work_path=store.work_path,
        test_suite_name=store.test_suite_name,
        mutation_suite_name=store.mutation_suite_name,
        mutation_timeout=store.mutation_timeout,
    )

    # Create Project (orchestration)
    project = Project(store, collector)

    return project


def from_project_info(
    name, path, work_dir, description=None, mutation_timeout=None
):
    """Create new project with initial configuration.

    This factory function creates a new work directory and initializes
    the project database with the provided metadata.

    Parameters
    ----------
    name : str
        Project name.
    path : str or Path
        Path to the project directory being analyzed.
    work_dir : str or Path
        Work directory path where yagua.db and temporary files will
        be stored (must not exist).
    description : str, optional
        Project description. Default is None.
    mutation_timeout : float, optional
        Timeout in seconds for mutation testing. Default is None.

    Returns
    -------
    Project
        Configured Project instance ready to run pipeline.

    Raises
    ------
    ValueError
        If work directory already exists.

    Examples
    --------
    >>> proj = from_project_info(
    ...     name="MyProject",
    ...     path="/path/to/project",
    ...     work_dir="/path/to/work_dir",
    ...     mutation_timeout=50.0
    ... )
    >>> proj.collect_tests()
    """
    # Test and mutation suite names are constants for now
    test_suite_name = "pytest"
    mutation_suite_name = "cosmic-ray"

    # Create ProjectStore (DAL) with initial data
    store = ProjectStore.from_project_info(
        name=name,
        path=path,
        work_dir=work_dir,
        description=description,
        mutation_timeout=mutation_timeout,
    )

    # Create Collector (suite execution)
    collector = Collector(
        project_path=store.path,
        project_name=store.name,
        work_path=store.work_path,
        test_suite_name=test_suite_name,
        mutation_suite_name=mutation_suite_name,
        mutation_timeout=mutation_timeout,
    )

    # Create Project (orchestration)
    project = Project(store, collector)

    return project
