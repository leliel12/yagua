"""
Yagua - Project Class.
"""

from pathlib import Path

from peewee import SqliteDatabase

from .models import BaseModel, ProjectModel, TestModel


# ============================================================================
# PROJECT CLASS
# ============================================================================


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
        cache_path: str | Path,
        name: str,
        path: str | Path,
        description: str | None = None,
    ):
        """
        Initialize a Project instance with a database cache path and project details.

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
        """
        self.cache_path = Path(cache_path)
        self.db = SqliteDatabase(str(self.cache_path))

        # Bind models to this database instance
        self.db.bind([BaseModel, ProjectModel, TestModel])

        # Ensure cache file and tables exist
        self._initialize_database()

        # Create or update the project in the database
        self.project = self._ensure_project(name, str(path), description)

    @classmethod
    def from_path(
        cls,
        project_path: str | Path,
        cache_path: str | Path,
        description: str | None = None,
    ) -> "Project":
        """
        Create a Project instance from a project directory path.

        This constructor creates a Project instance with the specified cache
        location for the given project path. The project name is derived from
        the directory name.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory.
        cache_path : str or Path
            Path where to create the cache database file.
        description : str, optional
            Project description.

        Returns
        -------
        Project
            A new Project instance with the specified cache path.
        """
        project_path_obj = Path(project_path).resolve()
        project_name = project_path_obj.name
        return cls(
            cache_path=cache_path,
            name=project_name,
            path=str(project_path_obj),
            description=description,
        )

    def _initialize_database(self):
        """
        Initialize the database and create tables if they don't exist.

        This method creates the cache file (if it doesn't exist) and
        ensures all required tables are created.
        """
        # Ensure parent directory exists
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect and create tables
        self.db.connect()
        self.db.create_tables([ProjectModel, TestModel], safe=True)

    def _ensure_project(
        self, name: str, path: str, description: str | None = None
    ) -> ProjectModel:
        """
        Create or update the single project in the database.

        Since each cache file represents exactly one project, this method
        ensures that there is always exactly one ProjectModel instance
        with id=1.

        Parameters
        ----------
        name : str
            Project name.
        path : str
            Project path.
        description : str, optional
            Project description.

        Returns
        -------
        ProjectModel
            The project model instance.
        """
        # Try to get the existing project (id=1)
        try:
            project = ProjectModel.get_by_id(1)
            # Update existing project
            project.name = name
            project.path = path
            if description is not None:
                project.description = description
            project.save()
        except ProjectModel.DoesNotExist:
            # Create new project with id=1
            project = ProjectModel.create(
                id=1,
                name=name,
                path=path,
                description=description,
            )

        return project

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
        tests = suite.collect_tests(self.project.path)

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
        return list(TestModel.select().where(TestModel.project == self.project))

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - closes database connection."""
        self.close()

    def __repr__(self):
        """String representation."""
        return f"Project(cache_path={self.cache_path})"
