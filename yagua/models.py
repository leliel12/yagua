"""
Yagua - Database Models.
"""

from datetime import datetime, timezone

from peewee import (
    Model,
    CharField,
    FloatField,
    ForeignKeyField,
    Check,
    DateTimeField,
    TextField,
)


# ============================================================================
# DATABASE MODELS
# ============================================================================


class BaseModel(Model):
    """Base model class that uses the database from the project instance.

    Attributes
    ----------
    created_at : DateTimeField
        UTC timestamp of when the record was created.
        Automatically set on creation.
    modified_at : DateTimeField
        UTC timestamp of when the record was last modified.
        Automatically updated on every save.
    """

    created_at = DateTimeField(default=lambda: datetime.now(timezone.utc))
    modified_at = DateTimeField(default=lambda: datetime.now(timezone.utc))

    def save(self, *args, **kwargs):
        """Override save to update modified_at timestamp."""
        self.modified_at = datetime.now(timezone.utc)
        return super().save(*args, **kwargs)


class ProjectModel(BaseModel):
    """Project information table.

    This table is limited to a single row per database.
    Each cache file represents exactly one project.
    The id must always be 1.

    Attributes
    ----------
    name : CharField
        Project name or identifier.
    path : CharField
        Filesystem path to the project directory.
    description : CharField, optional
        Optional project description.
    coverage : FloatField, optional
        Total project coverage percentage (0-100).
        Updated via collect-coverage command.

    Notes
    -----
    The Check constraint ensures only one row (id=1) can exist per database,
    enforcing the one-project-per-cache-file design.
    """

    name = CharField()
    path = CharField()
    description = CharField(null=True)
    coverage = FloatField(null=True, default=None)

    class Meta:
        # Ensure only one project per database
        # The id must always be 1
        constraints = [Check("id = 1")]


class HistoryModel(BaseModel):
    """Command history table.

    Records every command executed on a project, maintaining a complete
    audit log of operations performed on the project cache.

    Attributes
    ----------
    project : ForeignKeyField
        Reference to the ProjectModel (always id=1).
        Accessible via backref as project.history.
    tag : CharField
        Tag identifying the command type (e.g., 'collect_tests', 'collect_coverage::project').
    command : TextField
        The full command string that was executed (e.g., 'pytest --collect-only -q').
    stdout : TextField
        Standard output from the command execution.
    stderr : TextField
        Standard error output from the command execution.
    result : TextField
        Additional result data from the command execution.
        Can store JSON data or other structured information.

    Examples
    --------
    >>> HistoryModel.create(
    ...     project=project_model,
    ...     tag="collect_tests",
    ...     command="pytest --collect-only -q",
    ...     stdout="150 tests collected",
    ...     stderr="",
    ...     result="raw output data"
    ... )
    """

    project = ForeignKeyField(ProjectModel, backref="history")
    tag = CharField()
    command = TextField()
    stdout = TextField()
    stderr = TextField()
    result = TextField()


class TestModel(BaseModel):
    """Test information table.

    Stores individual test information and coverage metrics.

    Attributes
    ----------
    project : ForeignKeyField
        Reference to the ProjectModel (always id=1).
        Accessible via backref as project.tests.
    file : CharField
        Path to the test file relative to the project root.
    suite : CharField, optional
        Test suite or class name. None for standalone test functions.
    test : CharField
        Test function name.
    coverage_alone : FloatField, optional
        Coverage percentage when running this test in isolation.
        Not yet implemented.
    coverage_without : FloatField, optional
        Coverage percentage when running all tests except this one.
        Not yet implemented.

    Notes
    -----
    The unique constraint on (project, file, suite, test) ensures that
    each test is only stored once per project.
    """

    project = ForeignKeyField(ProjectModel, backref="tests")
    file = CharField()
    suite = CharField(null=True)
    test = CharField()
    coverage_alone = FloatField(null=True, default=None)
    coverage_without = FloatField(null=True, default=None)

    class Meta:
        indexes = ((("project", "file", "suite", "test"), True),)  # Unique constraint
