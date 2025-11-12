"""
Yagua - Database Models.
"""

from peewee import (
    Model,
    CharField,
    FloatField,
    ForeignKeyField,
    Check,
)


# ============================================================================
# DATABASE MODELS
# ============================================================================


class BaseModel(Model):
    """Base model class that uses the database from the project instance."""

    pass


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


class TestModel(BaseModel):
    """Test information table."""

    project = ForeignKeyField(ProjectModel, backref="tests")
    file = CharField()
    suite = CharField(null=True)
    test = CharField()
    coverage = FloatField(null=True, default=None)

    class Meta:
        indexes = ((("project", "file", "suite", "test"), True),)  # Unique constraint
