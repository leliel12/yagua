"""Yagua - Project Class.

This module provides the Project class, which serves as the main
interface for managing project databases, tests, and coverage
information. Each Project instance represents a single SQLite database
file containing one project's test data.

Classes
-------
Project : class
    Main project manager for QA testing, providing methods to collect tests,
    measure coverage, and query test information.

Architecture
------------
- Each Project instance creates its own SqliteDatabase connection
- Models are dynamically bound to the database via transaction()
  context manager
- All database operations are wrapped in transactions for ACID
  compliance
- The database schema is automatically created on first instantiation

Key Patterns
------------
1. **One Cache File Per Project**: Each SQLite file contains exactly
   one project
2. **Dynamic Model Binding**: Models are bound to database instances
   at runtime
3. **Transaction Management**: All DB operations use atomic
   transactions
"""

import contextlib
import types
from pathlib import Path

import pandas as pd
from peewee import SqliteDatabase

from .models import BaseModel, HistoryModel, ProjectModel, TestModel
from .mutationsuites import CosmicRaySuite
from .testsuites import PytestSuite


# ============================================================================
# CONSTANTS
# ============================================================================

#: Models that need to have tables created in the database.
#: These are the concrete models that store actual data.
#: BaseModel is excluded as it's abstract.
MODELS_TO_CREATE = [ProjectModel, TestModel, HistoryModel]

#: All models that need to be bound to the database instance.
#: Includes BaseModel since child models inherit from it and
#: the binding needs to propagate through the inheritance chain.
ALL_MODELS = [BaseModel] + MODELS_TO_CREATE

#: Available test suite handlers mapped by name.
#: Use these names in Project.from_project_info() to specify which
#: test framework the project uses.
TEST_SUITES = {
    "pytest": PytestSuite,
}

#: Available mutation suite handlers mapped by name.
#: Use these names in Project.from_project_info() to specify which
#: mutation testing framework the project uses.
MUTATION_SUITES = {
    "cosmic-ray": CosmicRaySuite,
}

# ============================================================================
# PROJECT CLASS
# ============================================================================


class Project:
    """Project manager for QA testing.

    This class manages the database connection and provides methods to
    interact with projects, tests, and execution history. The database
    instance is created per-project and models are dynamically bound to it.
    Each cache file represents a single project.

    Parameters
    ----------
    db_path : str or Path
        Path to the SQLite database cache file.

    Attributes
    ----------
    db : SqliteDatabase
        Database instance for this project. Models (ProjectModel, TestModel,
        HistoryModel) are bound to this instance via transaction contexts.

    Notes
    -----
    All database operations use the transaction() context manager which handles
    model binding and automatic transaction management (commit/rollback).
    """

    # ========================================================================
    # Constructor
    # ========================================================================

    def __init__(self, db_path):
        """Initialize Project with database path.

        Parameters
        ----------
        db_path : str or Path
            Path to SQLite database file.
        """
        self.db_path = db_path
        self.db = SqliteDatabase(str(db_path))
        self.db.connect()

        with self.transaction():
            self.db.create_tables(MODELS_TO_CREATE, safe=True)

    # ========================================================================
    # Alternative Constructors
    # ========================================================================

    @classmethod
    def from_project_info(
        cls, name, path, work_path, description, db_path
    ) -> "Project":
        """Create new Project with initial project information.

        Parameters
        ----------
        name : str
            Project name.
        path : str or Path
            Project directory path.
        work_path : str or Path
            Working directory for yagua operations (coverage, mutations, etc.).
        description : str, optional
            Project description.
        db_path : str or Path
            Path to SQLite database file (must not exist).

        Returns
        -------
        Project
            New Project instance with stored project information.

        Raises
        ------
        ValueError
            If database file already exists.
        """
        db_path = Path(db_path).resolve()
        if db_path.exists():
            raise ValueError(f"File {db_path} already exists")

        path = Path(path).resolve()
        work_path = Path(work_path).resolve()

        # at this points are contants
        test_suite_name = "pytest"
        mutation_suite_name = "cosmic-ray"

        project = cls(db_path)
        project.store_project_info(
            name,
            path,
            work_path,
            test_suite_name,
            mutation_suite_name,
            description,
        )

        return project

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def test_suite(self):
        """Get test suite handler instance for this project.

        Returns
        -------
        TestSuiteABC
            Instantiated test suite handler (e.g., PytestSuite) based on the
            project's test_suite_name configuration.

        Notes
        -----
        This property returns a new instance each time it's accessed. The
        suite class is looked up from TEST_SUITES dictionary using the
        project's test_suite_name field.
        """
        suite_cls = TEST_SUITES[self.test_suite_name]
        return suite_cls(self.work_path)

    @property
    def mutation_suite(self):
        """Get mutation testing suite handler instance for this project.

        Returns
        -------
        MutationSuiteABC
            Instantiated mutation suite handler based on the project's
            mutation_suite_name configuration.

        Notes
        -----
        This property returns a new instance each time it's accessed. The
        suite class is looked up from MUTATION_SUITES dictionary using the
        project's mutation_suite_name field.
        """
        suite_cls = MUTATION_SUITES[self.mutation_suite_name]
        return suite_cls(self.work_path)

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _get_project_model(self):
        """Get the project model from database.

        Returns
        -------
        ProjectModel
            The project model instance.
        """
        with self.transaction():
            return ProjectModel.get_by_id(1)

    @contextlib.contextmanager
    def transaction(self):
        """Context manager for database transactions with model binding.

        This method provides a context manager that:
        1. Binds all models to this project's database instance
        2. Opens an atomic transaction
        3. Automatically commits on success or rolls back on error

        Yields
        ------
        Transaction
            Database transaction context from Peewee.

        Notes
        -----
        All database operations should be wrapped in this context manager
        to ensure proper model binding and transaction management.
        """
        with self.db.bind_ctx(ALL_MODELS):
            with self.db.atomic() as txn:
                try:
                    yield txn
                    txn.commit()
                except Exception:
                    txn.rollback()

    # ========================================================================
    # Public Methods - Test Management
    # ========================================================================

    def collect_tests(self) -> tuple[int, int]:
        """Collect tests from a test suite and save them to the database.

        This method runs the suite's get_tests() method to discover all
        tests, saves them to the database, and logs the execution in the
        history table.

        Parameters
        ----------
        suite : TestSuiteABC
            Test suite handler with a get_tests() method (e.g., PytestSuite).

        Returns
        -------
        tuple[int, int]
            Tuple of (saved_count, updated_count) indicating the number
            of new tests saved and existing tests updated.

        Notes
        -----
        Creates a HistoryModel record with tag='collect_tests' containing
        the command executed and its output for audit purposes.
        """

        suite = self.test_suite
        result = suite.get_tests(self.path)

        saved_count = 0
        updated_count = 0
        with self.transaction():
            if not result.error:
                project = self._get_project_model()
                for test_id, file, suite_name, test in result.value:
                    _, created = self.add_test(
                        project=project,
                        test_id=test_id,
                        file=file,
                        suite=suite_name,
                        test=test,
                    )

                    if created:
                        saved_count += 1
                    else:
                        updated_count += 1

            HistoryModel.create(
                project=project,
                tag="collect_tests",
                command=result.command,
                status_code=result.status_code,
                stdout=result.stdout,
                stderr=result.stderr,
                result=result.result,
            )

        result.raise_if_error()

        return saved_count, updated_count

    def add_test(
        self,
        project,
        test_id: str,
        file: str,
        suite: str | None,
        test: str,
    ) -> tuple[TestModel, bool]:
        """Add or update a test in the database.

        Parameters
        ----------
        project : ProjectModel
            Project model instance.
        test_id : str
            Unique identifier for the test (usually the full pytest nodeid).
        file : str
            Test file path.
        suite : str, optional
            Test suite name.
        test : str
            Test name.

        Returns
        -------
        tuple[TestModel, bool]
            Tuple of (test, created) where created is True if the test
            was newly created.

        Notes
        -----
        Coverage information (coverage_alone, coverage_without) should be
        updated separately using collect_coverage_for_test() and
        collect_coverage_without_test() methods.
        """
        with self.transaction():
            test_obj, created = TestModel.get_or_create(
                project=project,
                test_id=test_id,
                file=file,
                suite=suite,
                test=test,
            )

        return test_obj, created

    def get_tests_dataframe(self) -> pd.DataFrame:
        """Get all tests for this project as a DataFrame.

        This method queries all tests from the database and converts them
        to a pandas DataFrame, including both regular fields and calculated
        hybrid properties (coverage_impact, coverage_uniqueness, etc.).

        Returns
        -------
        pd.DataFrame
            DataFrame containing all test information.

        Notes
        -----
        Calculated properties (coverage_impact, coverage_uniqueness, etc.)
        will be None if the required coverage data has not been collected yet.
        """
        # Helper function to group coverage columns (currently commented out)
        # def group_coverage_columns(columns):
        #     levels = []
        #     for c in columns:
        #         if c.startswith("coverage_"):
        #             sublevel = c.split("_", 1)[-1]
        #             levels.append(("coverage", sublevel))
        #         else:
        #             levels.append((None, c))
        #     return pd.MultiIndex.from_tuples(levels)

        with self.transaction():
            project = self._get_project_model()
            query = TestModel.select().where(TestModel.project == project)
            # Convert each model to dict using to_records() which
            # includes hybrid properties
            dicts = (dict(mdl.to_records()) for mdl in query)
            df = pd.DataFrame.from_dict(dicts)
            # Option to group coverage columns into multiindex
            # (currently disabled)
            # df.columns = group_coverage_columns(df.columns)

        return df

    def count_tests(self) -> int:
        """Count all tests for this project.

        Returns
        -------
        int
            Number of tests for the project.
        """
        with self.transaction():
            project = self._get_project_model()
            return (
                TestModel.select().where(TestModel.project == project).count()
            )

    def get_test(self, test_id: str | int) -> pd.Series:
        """Get a specific test by its test_id or database ID.

        This method retrieves a test from the database and returns it as
        a pandas Series with all fields and calculated properties. It supports
        lookup by both the database integer ID and the string test_id
        (pytest nodeid).

        Parameters
        ----------
        test_id : str | int
            Unique identifier for the test. Can be either:
            - int: Database primary key ID (e.g., 1, 2, 3)
            - str: Pytest nodeid (e.g., 'test_file.py::TestClass::test_method')

        Returns
        -------
        pd.Series
            Pandas Series containing all test fields and calculated properties
            (coverage_impact, coverage_overlap, coverage_uniqueness,
            coverage_redundancy). The series name is set to "test".

        Raises
        ------
        peewee.DoesNotExist
            If no test with the given test_id exists.
        """
        with self.transaction():
            # Build filter condition based on test_id type
            # Integer: lookup by database primary key ID
            # String: lookup by pytest nodeid (test_id field)
            flt = (
                (TestModel.id == test_id)
                if isinstance(test_id, int)
                else (TestModel.test_id == test_id)
            )

            # Retrieve test model instance
            test = TestModel.get(flt)

            # Convert to dictionary including hybrid properties
            test_dict = dict(test.to_records())

            # Convert to pandas Series for easier data manipulation
            series = pd.DataFrame.from_dict([test_dict]).iloc[0]
            series.name = "test"

            return series

    def _write_history(self, project, tag, result):
        return HistoryModel.create(
            project=project,
            tag=tag,
            command=result.command,
            status_code=result.status_code,
            stdout=result.stdout,
            stderr=result.stderr,
            result=result.result,
        )

    # ========================================================================
    # Public Methods - Coverage Management
    # ========================================================================

    def collect_coverage(self):
        """Collect and store coverage information for the project.

        This method runs the suite's get_coverage() method to execute tests
        with coverage enabled, stores the total coverage percentage in the
        ProjectModel, and logs the execution in the history table.

        Parameters
        ----------
        suite : TestSuiteABC
            Test suite handler with a get_coverage() method
            (e.g., PytestSuite).

        Returns
        -------
        float
            Total coverage percentage (0-100).

        Notes
        -----
        Creates a HistoryModel record with tag='collect_coverage'
        containing the command executed and its output for audit purposes.
        """
        suite = self.test_suite
        result = suite.get_coverage(self.path, self.name)

        with self.transaction():
            if not result.error:
                project = self._get_project_model()
                project.coverage = result.value
                project.save()

            self._write_history(
                project=project, tag="collect_coverage", result=result
            )

        result.raise_if_error()

        return result.value

    def collect_coverage_for_test(self, test_id):
        """Collect and store coverage for a single test in isolation.

        This method runs a specific test alone to measure its isolated
        coverage contribution. The result is stored in
        TestModel.coverage_alone.

        Parameters
        ----------
        suite : TestSuiteABC
            Test suite handler with a get_coverage_for_tests() method.
        test_id : str
            Unique test identifier (e.g., pytest node ID).

        Returns
        -------
        float
            Coverage percentage (0-100) for this test in isolation.

        Notes
        -----
        Creates a HistoryModel record with
        tag='collect_coverage_for_test::{test_id}' for tracking execution
        history per test.

        """
        suite = self.test_suite
        result = suite.get_coverage_for_tests(self.path, self.name, [test_id])

        with self.transaction():

            if not result.error:
                test = TestModel.get(TestModel.test_id == test_id)
                test.coverage_alone = result.value
                test.save()

            self._write_history(
                project=test.project,
                tag=f"collect_coverage_for_test::{test_id}",
                result=result,
            )

        result.raise_if_error()

        return result.value

    def collect_coverage_without_test(self, test_id):
        """Collect and store coverage when excluding a specific test.

        This method runs all tests except the specified one to measure
        coverage without that test's contribution. Useful for identifying
        test redundancy and dependencies. The result is stored in
        TestModel.coverage_without.

        Parameters
        ----------
        suite : TestSuiteABC
            Test suite handler with a get_coverage_for_tests() method.
        test_id : str
            Unique test identifier to exclude (e.g., pytest node ID).

        Returns
        -------
        float
            Coverage percentage (0-100) when running all tests except this one.

        Notes
        -----
        Creates a HistoryModel record with
        tag='collect_coverage_without_test::{test_id}'
        for tracking execution history. Queries all test IDs except the target
        and runs them together to measure combined coverage.
        """
        suite = self.test_suite
        with self.transaction():
            query = TestModel.select(TestModel.test_id).where(
                TestModel.test_id != test_id
            )
            tids_to_run = [test.test_id for test in query]

            result = suite.get_coverage_for_tests(
                self.path, self.name, tids_to_run
            )

            if not result.error:
                test = TestModel.get(TestModel.test_id == test_id)
                test.coverage_without = result.value
                test.save()

            self._write_history(
                project=test.project,
                tag=f"collect_coverage_without_test::{test_id}",
                result=result,
            )

        result.raise_if_error()

        return result.value

    # ========================================================================
    # Public Methods - Mutations Management
    # ========================================================================

    def collect_mutants(self, force=False):
        """Collect and store the number of mutants for the project.

        This method runs the mutation suite's get_mutants() method to
        initialize the mutation session and count the total number of
        mutants that will be generated. The result is stored in
        ProjectModel.mutants_number.

        Returns
        -------
        int
            Number of mutants generated for the project.

        Notes
        -----
        Creates a HistoryModel record with tag='collect_mutants'
        containing the command executed and its output for audit purposes.
        """
        suite = self.mutation_suite
        result = suite.get_mutants(self.path, self.name, force=force)

        with self.transaction():
            if not result.error:
                project = self._get_project_model()
                project.mutants_number = result.value
                project.save()

            self._write_history(
                project=project, tag="collect_mutants", result=result
            )

        result.raise_if_error()

        return result.value
    
    def test_mutations(self, force):
        suite = self.mutation_suite
        result = suite.test_mutations(self.path, self.name, force)

        with self.transaction():
            if not result.error:
                project = self._get_project_model()
                project.msr = result.value
                project.save()

            self._write_history(
                project=project, tag="test_mutations", result=result
            )

        result.raise_if_error()

        return result.value

    def collect_mutations_for_test(self, test_id):
        pass

    def collect_mutations_without_test(self, test_id):
        pass

    # ========================================================================
    # Public Methods - Project Information
    # ========================================================================

    def store_project_info(
        self,
        name: str,
        path: str,
        work_path: str,
        test_suite_name: str,
        mutation_suite_name: str,
        description: str | None = None,
    ) -> None:
        """Store or update project information in database.

        Parameters
        ----------
        name : str
            Project name.
        path : str
            Project path.
        work_path : str
            Working directory for yagua operations.
        test_suite_name : str
            Name of the test suite handler (e.g., 'pytest').
        mutation_suite_name : str
            Name of the mutation suite handler (e.g., 'cosmic-ray').
        description : str, optional
            Project description.
        """
        if test_suite_name not in TEST_SUITES:
            raise ValueError("[corregi claude]")
        if mutation_suite_name not in MUTATION_SUITES:
            raise ValueError("[corregi claude]")

        with self.transaction():
            project, created = ProjectModel.get_or_create(
                id=1,
                name=name,
                test_suite_name=test_suite_name,
                mutation_suite_name=mutation_suite_name,
                path=path,
                work_path=work_path,
                description=description,
            )
            if not created:
                project.name = name
                project.path = path
                project.work_path = work_path
                project.test_suite_name = test_suite_name
                project.mutation_suite_name = mutation_suite_name
                project.description = description
                project.save()

    # ========================================================================
    # Magic Methods
    # ========================================================================

    def close(self):
        """Close the database connection.

        This method should be called when done using the Project instance
        to properly close the database connection and release resources.
        """
        if not self.db.is_closed():
            self.db.close()

    def __getattr__(self, a):
        """Provide dynamic access to project model attributes.

        This magic method allows accessing ProjectModel fields directly
        through the Project instance
        (e.g., proj.name, proj.path, proj.coverage).

        Parameters
        ----------
        a : str
            Attribute name to access from ProjectModel.

        Returns
        -------
        Any
            Attribute value from the project model.

        Raises
        ------
        AttributeError
            If the attribute doesn't exist in ProjectModel.
        """
        if a not in dir(self):
            cls_name = type(self).__name__
            raise AttributeError(f"{cls_name!r} object has no attribute {a!r}")
        model = self._get_project_model()
        return getattr(model, a)

    def __dir__(self):
        """Expose project model fields in dir().

        This makes ProjectModel fields discoverable through autocomplete
        and dir() calls on the Project instance.

        Returns
        -------
        list
            List of available attributes including both Project instance
            attributes and ProjectModel fields (excluding 'id').
        """
        fields = [
            f for f in ProjectModel._meta.sorted_field_names if f != "id"
        ]
        return super().__dir__() + fields

    def __repr__(self):
        """Return string representation of Project instance.

        Returns
        -------
        str
            String in format "Project(db_path=<path>)".
        """
        return f"Project(db_path={self.db_path})"
