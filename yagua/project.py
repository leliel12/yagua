"""
Yagua - Project Class.
"""

import contextlib
from pathlib import Path
import types

from peewee import SqliteDatabase

from .models import BaseModel, ProjectModel, TestModel


# ============================================================================
# PROJECT CLASS
# ============================================================================

MODELS_TO_CREATE = [ProjectModel, TestModel]
ALL_MODELS = [BaseModel] + MODELS_TO_CREATE


class Project:
    """
    Project manager for QA testing.

    This class manages the database connection and provides methods to interact
    with projects and tests. The database instance is created per-project and
    models are bound to it. Each cache file represents a single project.

    Parameters
    ----------
    cache_path : str or Path
        Path to the SQLite database cache file.
    name : str
        Project name.
    path : str or Path
        Project path.
    description : str, optional
        Project description.

    Attributes
    ----------
    cache_path : Path
        Path to the SQLite database cache file.
    db : SqliteDatabase
        Database instance for this project.
    project : ProjectModel
        The project model instance for this project.
    """

    def __init__(
        self,
        db_path,
    ):
        self.db = SqliteDatabase(str(db_path))
        self.db.connect()

        with self.transaction():
            self.db.create_tables(MODELS_TO_CREATE, safe=True)

    @classmethod
    def from_project_info(
        cls,
        name,
        path,
        description,
        db_path,
    ) -> "Project":

        db_path = Path(db_path).resolve()
        if db_path.exists():
            raise ValueError(f"File {db_path} already exists")

        path = Path(path).resolve()
        db_path = Path(db_path).resolve()

        project = cls(db_path)
        project.store_project_info(name, path, description)

        return project

    @contextlib.contextmanager
    def transaction(self):
        with self.db.bind_ctx(ALL_MODELS):
            with self.db.atomic() as txn:
                try:
                    yield txn
                    txn.commit()
                except:
                    txn.rollback()

    def store_project_info(
        self, name: str, path: str, description: str | None = None
    ) -> ProjectModel:
        with self.transaction():
            project, created = ProjectModel.get_or_create(
                id=1, name=name, path=path, description=description
            )
            if not created:
                project.name = name
                project.path = path
                project.description = description
                project.save()

    def _get_project_model(self):
        with self.transaction():
            return ProjectModel.get_by_id(1)

    @property
    def name(self):
        return self._get_project_model().name

    @property
    def path(self):
        return self._get_project_model().path

    @property
    def description(self):
        return self._get_project_model().description

    def close(self):
        """Close the database connection."""
        if not self.db.is_closed():
            self.db.close()

    def add_test(
        self,
        file: str,
        suite: str | None,
        test: str,
        coverage: float | None = None,
    ) -> tuple[TestModel, bool]:
        """
        Add or update a test in the database.

        Parameters
        ----------
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
                project=self.project,
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

    def collect_tests(self, suite) -> tuple[int, int]:
        """
        Collect tests from a test suite and save them to the database.

        Parameters
        ----------
        suite : object
            A test suite object with a `collect_tests()` method that returns
            a list of tuples (file, suite, test).

        Returns
        -------
        tuple[int, int]
            Tuple of (saved_count, updated_count) indicating the number
            of new tests saved and existing tests updated.
        """
        with self.transaction():
            tests = suite.collect_tests(self.path)

            saved_count = 0
            updated_count = 0
            
            for file, suite_name, test in tests:
                _, created = self.add_test(
                    file=file,
                    suite=suite_name,
                    test=test,
                )

                if created:
                    saved_count += 1
                else:
                    updated_count += 1

        return saved_count, updated_count

    def list_tests(self) -> list[TestModel]:
        """
        List all tests for this project.

        Returns
        -------
        list[TestModel]
            List of all test models for the project.
        """
        with self.transaction():
            return list(
                TestModel.select().where(TestModel.project == self.project)
            )

    def __enter__(self):
        """Context manager entry."""
        self.db.connect(reuse_if_open=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - closes database connection."""
        self.close()

    def __repr__(self):
        """String representation."""
        return f"Project(cache_path={self.cache_path})"
