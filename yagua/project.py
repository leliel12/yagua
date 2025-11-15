"""
Yagua - Project Class.
"""

import contextlib
from pathlib import Path
import types

import pandas as pd

from peewee import SqliteDatabase

from .models import BaseModel, ProjectModel, TestModel, HistoryModel


# ============================================================================
# CONSTANTS
# ============================================================================

MODELS_TO_CREATE = [ProjectModel, TestModel, HistoryModel]
ALL_MODELS = [BaseModel] + MODELS_TO_CREATE


# ============================================================================
# PROJECT CLASS
# ============================================================================


class Project:
    """Project manager for QA testing.

    This class manages the database connection and provides methods to interact
    with projects, tests, and execution history. The database instance is created
    per-project and models are dynamically bound to it. Each cache file represents
    a single project.

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
        self.db = SqliteDatabase(str(db_path))
        self.db.connect()

        with self.transaction():
            self.db.create_tables(MODELS_TO_CREATE, safe=True)

    # ========================================================================
    # Alternative Constructors
    # ========================================================================

    @classmethod
    def from_project_info(cls, name, path, description, db_path) -> "Project":
        """Create new Project with initial project information.

        Parameters
        ----------
        name : str
            Project name.
        path : str or Path
            Project directory path.
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

        project = cls(db_path)
        project.store_project_info(name, path, description)

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
        """Context manager for database transactions.

        Yields
        ------
        Transaction
            Database transaction context.
        """
        with self.db.bind_ctx(ALL_MODELS):
            with self.db.atomic() as txn:
                try:
                    yield txn
                    txn.commit()
                except:
                    txn.rollback()

    # ========================================================================
    # Public Methods - Test Management
    # ========================================================================

    def collect_tests(self, suite) -> tuple[int, int]:
        """Collect tests from a test suite and save them to the database.

        This method runs the suite's get_tests() method to discover all tests,
        saves them to the database, and logs the execution in the history table.

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
        saved_count = 0
        updated_count = 0
        with self.transaction():
            tests, command, stdout, stderr, result = suite.get_tests(self.path)

            project = self._get_project_model()
            for test_id, file, suite_name, test in tests:
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
                command=command,
                stdout=stdout,
                stderr=stderr,
                result=result,
            )

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
        Coverage information (coverage_alone, coverage_without) is not yet
        implemented and should be updated separately once implemented.
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

        Returns
        -------
        pd.DataFrame
            DataFrame containing all test information including columns:
            id, project, file, suite, test, coverage_alone, coverage_without,
            created_at, modified_at.
        """
        with self.transaction():
            project = self._get_project_model()
            query = TestModel.select().where(TestModel.project == project)
            df = pd.DataFrame.from_dict(query.dicts())

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

    # ========================================================================
    # Public Methods - Coverage Management
    # ========================================================================

    def collect_coverage(self, suite):
        """Collect and store coverage information for the project.

        This method runs the suite's get_coverage() method to execute tests
        with coverage enabled, stores the total coverage percentage in the
        ProjectModel, and logs the execution in the history table.

        Parameters
        ----------
        suite : TestSuiteABC
            Test suite handler with a get_coverage() method (e.g., PytestSuite).

        Returns
        -------
        float
            Total coverage percentage (0-100).

        Notes
        -----
        Creates a HistoryModel record with tag='collect_coverage::project'
        containing the command executed and its output for audit purposes.
        """
        cov, command, stdout, stderr, result = suite.get_coverage(
            self.path, self.name
        )
        with self.transaction():
            project = self._get_project_model()
            project.coverage = cov
            project.save()

            HistoryModel.create(
                project=project,
                tag="collect_coverage::project",
                command=command,
                stdout=stdout,
                stderr=stderr,
                result=result,
            )
        return cov

    # ========================================================================
    # Public Methods - Project Information
    # ========================================================================

    def store_project_info(
        self, name: str, path: str, description: str | None = None
    ) -> None:
        """Store or update project information in database.

        Parameters
        ----------
        name : str
            Project name.
        path : str
            Project path.
        description : str, optional
            Project description.
        """
        with self.transaction():
            project, created = ProjectModel.get_or_create(
                id=1, name=name, path=path, description=description
            )
            if not created:
                project.name = name
                project.path = path
                project.description = description
                project.save()

    # ========================================================================
    # Magic Methods
    # ========================================================================

    def close(self):
        """Close the database connection."""
        if not self.db.is_closed():
            self.db.close()

    def __getattr__(self, a):
        """Provide dynamic access to project model attributes.

        Parameters
        ----------
        a : str
            Attribute name.

        Returns
        -------
        Any
            Attribute value from project model.

        Raises
        ------
        AttributeError
            If attribute doesn't exist.
        """
        if a not in dir(self):
            raise AttributeError(a)
        model = self._get_project_model()
        return getattr(model, a)

    def __dir__(self):
        """Expose project model fields in dir().

        Returns
        -------
        list
            List of available attributes.
        """
        fields = [
            f for f in ProjectModel._meta.sorted_field_names if f != "id"
        ]
        return super().__dir__() + fields

    def __enter__(self):
        """Context manager entry."""
        self.db.connect(reuse_if_open=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - closes database connection."""
        self.close()

    def __repr__(self):
        """String representation."""
        return f"Project(db_path={self.db.database})"
