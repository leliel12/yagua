"""
Yagua - Project Class.
"""

import contextlib
from pathlib import Path
import types

import pandas as pd

from peewee import SqliteDatabase

from .models import BaseModel, ProjectModel, TestModel


# ============================================================================
# CONSTANTS
# ============================================================================

MODELS_TO_CREATE = [ProjectModel, TestModel]
ALL_MODELS = [BaseModel] + MODELS_TO_CREATE


# ============================================================================
# PROJECT CLASS
# ============================================================================


class Project:
    """Project manager for QA testing.

    This class manages the database connection and provides methods to interact
    with projects and tests. The database instance is created per-project and
    models are bound to it. Each cache file represents a single project.

    Parameters
    ----------
    db_path : str or Path
        Path to the SQLite database cache file.

    Attributes
    ----------
    db : SqliteDatabase
        Database instance for this project.
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

        Parameters
        ----------
        suite : PytestSuite
            Test suite object with a get_tests() method.

        Returns
        -------
        tuple[int, int]
            Tuple of (saved_count, updated_count) indicating the number
            of new tests saved and existing tests updated.
        """
        with self.transaction():
            tests = suite.get_tests(self.path)

            saved_count = 0
            updated_count = 0

            project = self._get_project_model()
            for file, suite_name, test in tests:
                _, created = self.add_test(
                    project=project,
                    file=file,
                    suite=suite_name,
                    test=test,
                )

                if created:
                    saved_count += 1
                else:
                    updated_count += 1

        return saved_count, updated_count

    def add_test(
        self,
        project,
        file: str,
        suite: str | None,
        test: str,
        coverage: float | None = None,
    ) -> tuple[TestModel, bool]:
        """Add or update a test in the database.

        Parameters
        ----------
        project : ProjectModel
            Project model instance.
        file : str
            Test file path.
        suite : str, optional
            Test suite name.
        test : str
            Test name.
        coverage : float, optional
            Test coverage percentage.

        Returns
        -------
        tuple[TestModel, bool]
            Tuple of (test, created) where created is True if the test
            was newly created.
        """
        with self.transaction():
            test_obj, created = TestModel.get_or_create(
                project=project,
                file=file,
                suite=suite,
                test=test,
                defaults={"coverage": coverage},
            )

            if not created and coverage is not None:
                # Update coverage if provided
                test_obj.coverage = coverage
                test_obj.save()

        return test_obj, created

    def list_tests(self) -> pd.DataFrame:
        """List all tests for this project as a DataFrame.

        Returns
        -------
        pd.DataFrame
            DataFrame containing all test information.
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

        Parameters
        ----------
        suite : PytestSuite
            Test suite object with a get_coverage() method.

        Returns
        -------
        float
            Coverage percentage.
        """
        cov = suite.get_coverage(self.path, self.name)
        with self.transaction():
            project = self._get_project_model()
            project.coverage = cov
            project.save()
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
        fields = [f for f in ProjectModel._meta.sorted_field_names if f != "id"]
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
