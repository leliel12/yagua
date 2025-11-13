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
    command : CharField
        The command that was executed (e.g., 'collect-tests', 'collect-coverage').
    output : CharField
        The output or result of the command execution.
        Can store status messages, error messages, or summary information.

    Examples
    --------
    >>> HistoryModel.create(
    ...     project=project_model,
    ...     tag="some command"
    ...     command="collect-tests",
    ...     output="Collected 150 tests, 10 new, 5 updated"
    ... )
    """

    project = ForeignKeyField(ProjectModel, backref="history")
    tag = CharField()
    command = TextField()
    stdout = TextField()
    stderr = TextField()
    result = TextField()


class TestModel(BaseModel):
    """Test information table."""

    project = ForeignKeyField(ProjectModel, backref="tests")
    file = CharField()
    suite = CharField(null=True)
    test = CharField()
    coverage_alone = FloatField(null=True, default=None)
    coverage_without = FloatField(null=True, default=None)

    class Meta:
        indexes = ((("project", "file", "suite", "test"), True),)  # Unique constraint
