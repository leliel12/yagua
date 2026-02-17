"""Yagua - ProjectStore Class (Data Access Layer).

This module provides the ProjectStore class, which serves as the
data access layer (DAL) for managing project databases, tests, and
history records. Each ProjectStore instance represents a single
SQLite database file containing one project's data.

The ProjectStore class is responsible exclusively for CRUD
operations and transactions. All business logic, suite execution,
and pipeline management are handled by Project.

Classes
-------
ProjectStore : class
    Data access layer for project database operations, providing
    methods to save/query tests, coverage, mutations, and history.

Architecture
------------
- Each ProjectStore instance creates its own SqliteDatabase
  connection
- Models are dynamically bound to the database via transaction()
  context manager
- All database operations are wrapped in transactions for ACID
  compliance
- The database schema is automatically created on first
  instantiation

Key Patterns
------------
1. **One Work Directory Per Project**: Each work directory contains
   exactly one project database
2. **Dynamic Model Binding**: Models are bound to database instances
   at runtime
3. **Transaction Management**: All DB operations use atomic
   transactions
4. **Pure DAL**: No suite execution or business logic; only
   database read/write operations
"""

import contextlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from peewee import SqliteDatabase

from .. import io as yagua_io
from ..utils.bunch import Bunch
from .models import (
    BaseModel,
    EntropyMeasurementModel,
    HistoryModel,
    ProjectModel,
    TestModel,
)


# ============================================================================
# CONSTANTS
# ============================================================================

#: Models that need to have tables created in the database.
#: These are the concrete models that store actual data.
#: BaseModel is excluded as it's abstract.
MODELS_TO_CREATE = [
    ProjectModel,
    TestModel,
    HistoryModel,
    EntropyMeasurementModel,
]

#: All models that need to be bound to the database instance.
#: Includes BaseModel since child models inherit from it and
#: the binding needs to propagate through the inheritance chain.
ALL_MODELS = [BaseModel] + MODELS_TO_CREATE

# ============================================================================
# PROJECT STORE CLASS
# ============================================================================


@dataclass(frozen=True)
class _ProjectTransaction:
    """Wrapper around a database transaction with model access.

    Attributes
    ----------
    transaction : object
        Peewee atomic transaction context.
    models : Bunch
        Bunch of bound model classes.
    """

    transaction: object
    models: Bunch

    def __getattr__(self, attr):
        return getattr(self.transaction, attr)

    @property
    def project_model(self):
        """Get the project model instance (id=1)."""
        return self.models.ProjectModel.get_by_id(1)

    @property
    def m(self):
        """Get the models Bunch."""
        return self.models


class ProjectStore:
    """Data access layer for project database operations.

    This class manages the database connection and provides methods to
    save and query projects, tests, and execution history. The database
    instance is created per-project and models are dynamically bound
    to it. Each work directory represents a single project.

    All suite execution and business logic is handled by
    Project; this class only performs database operations.

    Parameters
    ----------
    work_dir : str or Path
        Path to the project's work directory. The database file (yagua.db)
        will be located inside this directory along with all temporary files.

    Attributes
    ----------
    work_dir : Path
        Work directory for this project containing the database and
        temporary files.
    db_path : Path
        Path to the SQLite database file (work_dir/yagua.db).
    db : SqliteDatabase
        Database instance for this project. Models (ProjectModel, TestModel,
        HistoryModel) are bound to this instance via transaction contexts.

    Notes
    -----
    All database operations use the transaction() context manager which handles
    model binding and automatic transaction management (commit/rollback).

    The work directory structure:
    work_dir/
    ├── yagua.db           # Main database file
    └── [temp files]       # Framework-specific temporary files
    """

    # ========================================================================
    # Constructor
    # ========================================================================

    def __init__(self, work_dir):
        """Initialize ProjectStore with work directory.

        Parameters
        ----------
        work_dir : str or Path
            Path to work directory containing yagua.db and temporary files.
        """
        self.work_dir = Path(work_dir).resolve()
        self.db_path = self.work_dir / "yagua.db"
        self.db = SqliteDatabase(str(self.db_path))
        self.db.connect()

        # store the models as bunch for convenience
        models_dict = {model.__name__: model for model in MODELS_TO_CREATE}
        self._models = Bunch("models", models_dict)

        with self.transaction():
            self.db.create_tables(MODELS_TO_CREATE, safe=True)

    # ========================================================================
    # Alternative Constructors
    # ========================================================================

    @classmethod
    def from_project_info(
        cls, name, path, work_dir, description=None, mutation_timeout=None
    ) -> "ProjectStore":
        """Create new ProjectStore with initial project information.

        This method creates a new work directory and initializes a project
        database inside it with the provided metadata.

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
        ProjectStore
            New ProjectStore instance with stored project information.

        Raises
        ------
        ValueError
            If work directory already exists.

        Notes
        -----
        The work directory will be created by this method and will contain:
        - yagua.db: SQLite database with project metadata and test data
        - Temporary files from test/mutation frameworks
        """
        work_dir = Path(work_dir).resolve()
        if work_dir.exists():
            raise ValueError(
                f"Work directory {work_dir} already exists. "
                "Please choose a different directory "
                "or remove the existing one."
            )

        path = Path(path).resolve()

        # Create work directory
        work_dir.mkdir(parents=True, exist_ok=False)

        # Test and mutation suite names are constants for now
        test_suite_name = "pytest"
        mutation_suite_name = "cosmic-ray"

        project = cls(work_dir)
        project.store_project_info(
            name,
            path,
            work_dir,
            test_suite_name,
            mutation_suite_name,
            description,
            mutation_timeout,
        )

        return project

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
        txn = None
        with self.db.bind_ctx(ALL_MODELS):
            with self.db.atomic() as txn:
                try:

                    prj_transaction = _ProjectTransaction(
                        transaction=txn, models=self._models
                    )
                    yield prj_transaction
                    txn.commit()
                except Exception:
                    if txn:
                        txn.rollback()
                    raise

    # ========================================================================
    # Public Methods - Test Management
    # ========================================================================

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
        updated separately using save_test_coverage_alone() and
        save_test_coverage_without() methods.
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
        to a pandas DataFrame, including both regular fields and hybrid
        properties (mutants_survived_alone, mutants_killed_alone, etc.).

        Returns
        -------
        pd.DataFrame
            DataFrame containing all test information.

        Notes
        -----
        Hybrid properties (mutants_survived_alone, mutants_killed_alone,
        mutants_survived_without, mutants_killed_without) will be None
        if the required mutation data has not been collected yet.
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

    def create_entropy_measurements(self, *, ordering_method, ascending):
        """Create entropy measurement records for ordered tests.

        Parameters
        ----------
        ordering_method : str
            Metric used to order tests.
        ascending : bool
            Whether to sort in ascending order.

        Returns
        -------
        dict
            Dictionary with 'created' key indicating number of
            records created.
        """
        creations = 0
        with self.transaction() as txn:
            project = txn.project_model
            EntropyMeasurementModel = txn.m.EntropyMeasurementModel

            filter = (
                EntropyMeasurementModel.ordering_method == ordering_method,
                EntropyMeasurementModel.ascending == ascending,
            )
            query = project.entropy_measurements.select().where(*filter)

            if not query.exists():
                tests = sorted(
                    [t for t in project.tests.select()],
                    key=(lambda t: getattr(t, ordering_method)),
                    reverse=not ascending,
                )
                tests_ids = []
                for test in tests:
                    tests_ids.append(test.test_id)

                    _, created = EntropyMeasurementModel.get_or_create(
                        project=project,
                        ordering_method=ordering_method,
                        ascending=ascending,
                        tests_count=len(tests_ids),
                        defaults={"tests_ids": tests_ids},
                    )
                    creations += int(created)

            return {"created": creations}

    def get_entropy_dataframe(
        self, *, ordering_method, ascending
    ) -> pd.DataFrame:
        """Get entropy measurements as a DataFrame.

        Parameters
        ----------
        ordering_method : str
            Metric used to order tests.
        ascending : bool
            Whether tests were sorted in ascending order.

        Returns
        -------
        pd.DataFrame
            DataFrame with entropy measurements ordered by
            test_count descending.
        """

        with self.transaction() as txn:
            project = txn.project_model
            EntropyMeasurementModel = txn.m.EntropyMeasurementModel

            filter = (
                EntropyMeasurementModel.ordering_method == ordering_method,
                EntropyMeasurementModel.ascending == ascending,
            )
            query = project.entropy_measurements.select().where(*filter)
            query = query.order_by(EntropyMeasurementModel.tests_count)

            # Convert each model to dict using to_records() which
            # includes hybrid properties
            dicts = (dict(mdl.to_records()) for mdl in query)
            df = pd.DataFrame.from_dict(dicts)

        return df

    def count_tests(self) -> int:
        """Count all tests for this project.

        Returns
        -------
        int
            Number of tests for the project.
        """
        with self.transaction() as txn:
            project = txn.project_model
            return project.tests.count()

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
            Pandas Series containing all test fields and hybrid properties
            (mutants_survived_alone, mutants_killed_alone,
            mutants_survived_without, mutants_killed_without).
            The series name is set to "test".

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
        """Create a history record in the database.

        Parameters
        ----------
        project : ProjectModel
            Project model instance.
        tag : str
            Tag identifying the operation.
        result : object
            Result object with command execution details.

        Returns
        -------
        HistoryModel
            Created history model instance.
        """
        return HistoryModel.create(
            project=project,
            tag=tag,
            command=result.command,
            status_code=result.status_code,
            stdout=result.stdout,
            stderr=result.stderr,
            result=result.result,
        )

    def write_history(self, tag, result, project=None):
        """Write a history entry to the database.

        Parameters
        ----------
        tag : str
            History tag identifying the operation.
        result : object
            Result object with command, status_code, stdout, stderr,
            and result attributes.
        project : ProjectModel, optional
            Project model instance. If None, fetches from database.

        Returns
        -------
        HistoryModel
            Created history model instance.
        """
        with self.transaction():
            if project is None:
                project = self._get_project_model()
            return self._write_history(project, tag, result)

    def get_test_ids_except(self, excluded_test_id):
        """Get all test IDs except the specified one.

        Parameters
        ----------
        excluded_test_id : str
            Test ID to exclude from the results.

        Returns
        -------
        list[str]
            List of test IDs excluding the specified one.
        """
        with self.transaction():
            query = TestModel.select(TestModel.test_id).where(
                TestModel.test_id != excluded_test_id
            )
            return [test.test_id for test in query]

    # ========================================================================
    # Public Methods - Save Operations (DAL)
    # ========================================================================

    def save_tests(self, *, tests_data, result):
        """Save collected tests and write history in a transaction.

        Parameters
        ----------
        tests_data : list[tuple]
            List of (test_id, file, suite_name, test) tuples.
        result : object
            Result object from the test suite execution.

        Returns
        -------
        tuple[int, int]
            Tuple of (saved_count, updated_count).
        """
        saved_count = 0
        updated_count = 0
        with self.transaction():
            project = self._get_project_model()
            if not result.error:
                for test_id, file, suite_name, test in tests_data:
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

            self._write_history(project, "collect_tests", result)

        return saved_count, updated_count

    def save_coverage(self, *, value, result):
        """Save project coverage value and write history.

        Parameters
        ----------
        value : float
            Coverage proportion to store (0-1).
        result : object
            Result object from the test suite execution.

        Returns
        -------
        float
            The coverage value.
        """
        with self.transaction():
            project = self._get_project_model()
            if not result.error:
                project.coverage = value
                project.save()

            self._write_history(project, "collect_coverage", result)

        return value

    def save_test_coverage_alone(self, *, test_id, value, result):
        """Save isolated coverage for a single test and write history.

        Parameters
        ----------
        test_id : str
            Unique test identifier.
        value : float
            Coverage proportion when running only this test (0-1).
        result : object
            Result object from the test suite execution.

        Returns
        -------
        float
            The coverage value.
        """
        with self.transaction():
            project = self._get_project_model()
            if not result.error:
                test = TestModel.get(TestModel.test_id == test_id)
                test.coverage_alone = value
                test.save()

            self._write_history(
                project,
                f"collect_coverage_for_test::{test_id}",
                result,
            )

        return value

    def save_test_coverage_without(self, *, test_id, value, result):
        """Save coverage-without for a single test and write history.

        Parameters
        ----------
        test_id : str
            Unique test identifier to exclude.
        value : float
            Coverage proportion when running all tests except this
            one (0-1).
        result : object
            Result object from the test suite execution.

        Returns
        -------
        float
            The coverage value.
        """
        with self.transaction():
            project = self._get_project_model()
            if not result.error:
                test = TestModel.get(TestModel.test_id == test_id)
                test.coverage_without = value
                test.save()

            self._write_history(
                project,
                f"collect_coverage_without_test::{test_id}",
                result,
            )

        return value

    def save_mutants_number(self, *, value, result):
        """Save project mutants number and write history.

        Parameters
        ----------
        value : int
            Number of mutants generated.
        result : object
            Result object from the mutation suite execution.

        Returns
        -------
        int
            The mutants number.
        """
        with self.transaction():
            project = self._get_project_model()
            if not result.error:
                project.mutants_number = value
                project.save()

            self._write_history(project, "collect_mutants", result)

        return value

    def save_msr(self, *, value, result):
        """Save project mutation survival rate and write history.

        Parameters
        ----------
        value : float
            Mutation survival rate proportion (0-1).
        result : object
            Result object from the mutation suite execution.

        Returns
        -------
        float
            The MSR value.
        """
        with self.transaction():
            project = self._get_project_model()
            if not result.error:
                project.msr = value
                project.save()

            self._write_history(project, "get_survival_rate", result)

        return value

    def save_test_msr_alone(self, *, test_id, value, result):
        """Save isolated MSR for a single test and write history.

        Parameters
        ----------
        test_id : str
            Unique test identifier.
        value : float
            MSR proportion when running only this test (0-1).
        result : object
            Result object from the mutation suite execution.

        Returns
        -------
        float
            The MSR value.
        """
        with self.transaction():
            project = self._get_project_model()
            if not result.error:
                test = TestModel.get(TestModel.test_id == test_id)
                test.msr_alone = value
                test.save()

            self._write_history(
                project,
                f"collect_survival_rate_for_test::{test_id}",
                result,
            )

        return value

    def save_test_msr_without(self, *, test_id, value, result):
        """Save MSR-without for a single test and write history.

        Parameters
        ----------
        test_id : str
            Unique test identifier to exclude.
        value : float
            MSR proportion when running all tests except this one
            (0-1).
        result : object
            Result object from the mutation suite execution.

        Returns
        -------
        float
            The MSR value.
        """
        with self.transaction():
            project = self._get_project_model()
            if not result.error:
                test = TestModel.get(TestModel.test_id == test_id)
                test.msr_without = value
                test.save()

            self._write_history(
                project,
                f"collect_survival_rate_without_test::{test_id}",
                result,
            )

        return value

    def save_entropy_measurement(
        self, *, ordering_method, ascending, test_count, msr, result
    ):
        """Save MSR for an entropy measurement record and write history.

        Parameters
        ----------
        ordering_method : str
            Metric used to order tests.
        ascending : bool
            Whether tests were sorted in ascending order.
        test_count : int
            Number of tests in this incremental suite.
        msr : float
            Mutation survival rate for this incremental suite (0-1).
        result : object or None
            Result object from the mutation suite execution, or None
            when reusing the full test suite's existing MSR.

        Returns
        -------
        float
            The MSR value.
        """
        with self.transaction() as txn:
            project = txn.project_model
            EntropyMeasurementModel = txn.m.EntropyMeasurementModel

            record = EntropyMeasurementModel.get(
                EntropyMeasurementModel.project == project,
                EntropyMeasurementModel.ordering_method == ordering_method,
                EntropyMeasurementModel.ascending == ascending,
                EntropyMeasurementModel.tests_count == test_count,
            )
            if result is None or not result.error:
                record.msr = msr
                record.save()

            if result is not None:
                self._write_history(
                    project,
                    f"collect_entropy_msr::{ordering_method}::{ascending}"
                    f"::{test_count}",
                    result,
                )

        return msr

    # ========================================================================
    # Public Methods - Project Information
    # ========================================================================

    def update_pipeline_step(self, new_step: str) -> None:
        """Update the pipeline step in the database.

        This method updates the pipeline step without validation.
        Validation should be performed by the caller (Project).

        Parameters
        ----------
        new_step : str
            New pipeline step to set.

        Notes
        -----
        This method does not validate the step order or validity.
        Use Project for proper pipeline validation and updates.
        """
        with self.transaction():
            proj_model = self._get_project_model()
            proj_model.pipeline_step = new_step
            proj_model.save()

    def store_project_info(
        self,
        name: str,
        path: str,
        work_path: str,
        test_suite_name: str,
        mutation_suite_name: str,
        description: str | None = None,
        mutation_timeout: float | None = 10,
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
        mutation_timeout : float, optional
            Timeout in seconds for mutation testing.
        """
        with self.transaction():
            project, created = ProjectModel.get_or_create(
                id=1,
                name=name,
                test_suite_name=test_suite_name,
                mutation_suite_name=mutation_suite_name,
                path=path,
                work_path=work_path,
                description=description,
                mutation_timeout=mutation_timeout,
            )
            if not created:
                project.name = name
                project.path = path
                project.work_path = work_path
                project.test_suite_name = test_suite_name
                project.mutation_suite_name = mutation_suite_name
                project.description = description
                project.mutation_timeout = mutation_timeout
                project.save()

    def export(self, output_path=None):
        """Export the work directory to an archive file.

        This method creates an archive file containing the complete work
        directory, including the yagua.db database and all temporary
        files generated by test and mutation frameworks. The archive
        format is determined by the file extension.

        Parameters
        ----------
        output_path : str or Path, optional
            Path where the archive will be created, including the desired
            extension (e.g., 'backup.zip', 'backup.tar.gz'). If not
            provided, defaults to '<work_dir_name>.zip' in the current
            directory. Supported formats: zip, tar, tar.gz (tgz), tar.bz2
            (tbz2), tar.xz (txz).

        Returns
        -------
        Path
            Path to the created archive file.

        Raises
        ------
        ValueError
            If the archive format is not supported.

        Notes
        -----
        The archive preserves the complete directory structure and can be
        used to backup, share, or restore a yagua project. The format is
        automatically detected from the file extension.

        Supported formats:
        - .zip: ZIP archive
        - .tar: Uncompressed TAR archive
        - .tar.gz or .tgz: Gzipped TAR archive
        - .tar.bz2 or .tbz2: Bzip2 compressed TAR archive
        - .tar.xz or .txz: XZ compressed TAR archive

        See Also
        --------
        yagua.io.export_work_dir : Lower-level export function.
        yagua.io.import_archive : Import an archive file.
        """
        # Close database connection before archiving
        self.close()

        try:
            # Use io module function for export
            return yagua_io.export_work_dir(self.work_dir, output_path)
        finally:
            # Reconnect to database
            self.db.connect()

    # ========================================================================
    # Magic Methods
    # ========================================================================

    def close(self):
        """Close the database connection.

        This method should be called when done using the ProjectStore
        instance to properly close the database connection and release
        resources.
        """
        if not self.db.is_closed():
            self.db.close()

    def __getattr__(self, a):
        """Provide dynamic access to project model attributes.

        This magic method allows accessing ProjectModel fields directly
        through the ProjectStore instance
        (e.g., store.name, store.path, store.coverage).

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
        and dir() calls on the ProjectStore instance.

        Returns
        -------
        list
            List of available attributes including both Project instance
            attributes and ProjectModel fields (excluding 'id').
        """
        fields = [
            f for f in ProjectModel._meta.sorted_field_names if f != "id"
        ] + list(ProjectModel._hproperties())
        return super().__dir__() + fields

    def __repr__(self):
        """Return string representation of ProjectStore instance.

        Returns
        -------
        str
            String in format "ProjectStore(work_dir=<path>)".
        """
        return f"ProjectStore(work_dir={self.work_dir})"

    @property
    def mutation_active_test_ratio(self):
        """Calculate the ratio of mutation-active tests in the test suite.

        This metric measures the proportion of tests that kill at least one
        mutant when run in isolation. It provides a simple indicator of how
        many tests in the suite actively contribute to mutation detection.

        Returns
        -------
        float
            Ratio of mutation-active tests, a value between 0 and 1:
            - 1.0: All tests kill at least one mutant (all tests are active)
            - 0.5: Half of the tests kill mutants
            - 0.0: No tests kill mutants (test suite is ineffective)

        Formula
        -------
        ratio = |{t : mutants_killed_alone(t) > 0}| / N

        where N is the total number of tests in the suite.

        Notes
        -----
        - A test is considered "mutation-active" if mutants_killed_alone > 0
        - Requires mutation testing data to be collected
        - Low values suggest many tests are redundant or ineffective
        - This is a simpler metric than MTI (macrostate_tightness_ratio)

        See Also
        --------
        macrostate_tightness_ratio : More sophisticated entropy-based metric
        TestModel.mutants_killed_alone : Mutants killed by each test alone

        """
        with self.transaction():
            proj = self._get_project_model()
            tests_number = proj.tests.count()

            mutants_killed_alones = np.array(
                [
                    test.mutants_killed_alone
                    for test in TestModel.select()
                    if test.mutants_killed_alone > 0
                ]
            )
            ratio = len(mutants_killed_alones) / tests_number
            return ratio

    # paper alias
    mti1 = mutation_active_test_ratio

    @property
    def macrostate_tightness_ratio(self):
        """Calculate the macrostate tightness index (MTI) for the test suite.

        This method computes a normalized entropy-based metric that measures
        how evenly the mutation-killing capability is distributed across the
        test suite. It uses the Shannon entropy of mutation kill impacts,
        normalized by the logarithm of the test count.

        Returns
        -------
        float
            Macrostate Tightness Index (MTI), a value between 0 and 1:
            - Values near 1: mutation-killing capability is evenly distributed
              across tests (high redundancy, balanced test suite)
            - Values near 0: capability is concentrated in a few tests
              (low redundancy, unbalanced test suite)

        Formula
        -------
        MTI = -sum(w_i * log(w_i)) / log(N)

        where:
        - w_i = mk_impact_i / sum(mk_impacts) are normalized weights
        - N is the total number of tests
        - mk_impact_i is the number of mutants exclusively killed by test i

        Notes
        -----
        - Only tests with mk_impact > 0 are included in the calculation
        - Requires mutation testing data to be collected
        - Based on information theory entropy concepts
        - Higher MTI suggests more redundancy in the test suite

        See Also
        --------
        TestModel.mk_impact : Mutants exclusively killed by each test

        """
        with self.transaction():
            proj = self._get_project_model()
            log_tests_number = np.log(proj.tests.count())

            information_weights = np.array(
                [
                    test.information_weights
                    for test in TestModel.select()
                    if test.mutants_killed_alone > 0
                ]
            )

            the_mti2 = (
                -np.sum(information_weights * np.log(information_weights))
                / log_tests_number
            )
            return the_mti2

    # paper alias
    mti2 = macrostate_tightness_ratio
