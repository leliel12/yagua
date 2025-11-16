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
        Tag identifying the command type with optional test context
        (e.g., 'collect_tests', 'collect_coverage',
        'collect_coverage_for_test::{test_id}',
        'collect_coverage_without_test::{test_id}').
    command : TextField
        The full command string that was executed
        (e.g., 'pytest --collect-only -q').
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
    test_id : CharField
        Unique identifier for the test (usually the full pytest nodeid).
    file : CharField
        Path to the test file relative to the project root.
    suite : CharField, optional
        Test suite or class name. None for standalone test functions.
    test : CharField
        Test function name.
    coverage_alone : FloatField, optional
        Coverage percentage when running this test in isolation (0-100).
        Updated via collect-coverage command with per-test analysis.
    coverage_without : FloatField, optional
        Coverage percentage when running all tests except this one (0-100).
        Updated via collect-coverage command, useful for identifying
        test redundancy and dependencies.

    Calculated Properties
    ---------------------
    coverage_impact : float | None
        Impact on total coverage (unique contribution).
        Calculated as: total_coverage - coverage_without
        Requires: project.coverage and coverage_without
    coverage_overlap : float | None
        Coverage shared with other tests.
        Calculated as: total_coverage - coverage_alone
        Requires: project.coverage and coverage_alone
    coverage_uniqueness : float | None
        Percentage of test's coverage that is unique (0-100).
        Calculated as: (coverage_impact / coverage_alone) * 100
        Requires: coverage_alone and coverage_impact
    coverage_redundancy : float | None
        Percentage of test's coverage that is redundant (0-100).
        Calculated as: ((coverage_alone - coverage_impact) / coverage_alone) * 100
        Requires: coverage_alone and coverage_impact

    Notes
    -----
    The test_id field is unique across all tests and typically contains
    the full pytest nodeid (e.g., 'file.py::TestClass::test_method').
    Additionally, there is a unique constraint on (project, file, suite, test)
    to ensure each test is only stored once per project.

    Calculated properties return None if required data is not available.
    """

    project = ForeignKeyField(ProjectModel, backref="tests")
    test_id = CharField(unique=True)
    file = CharField()
    suite = CharField(null=True)
    test = CharField()
    coverage_alone = FloatField(null=True, default=None)
    coverage_without = FloatField(null=True, default=None)

    @property
    def coverage_impact(self) -> float | None:
        """Calculate impact on total coverage (unique contribution).

        Returns
        -------
        float | None
            Impact percentage, or None if data unavailable.

        Formula
        -------
        coverage_impact = total_coverage - coverage_without

        This represents how much coverage would be lost if this test
        were removed from the test suite.
        """
        if self.project.coverage is None or self.coverage_without is None:
            return None
        return self.project.coverage - self.coverage_without

    @property
    def coverage_overlap(self) -> float | None:
        """Calculate coverage shared with other tests.

        Returns
        -------
        float | None
            Overlap percentage, or None if data unavailable.

        Formula
        -------
        coverage_overlap = total_coverage - coverage_alone

        This represents how much of the total coverage is NOT unique
        to this test (i.e., covered by other tests as well).
        """
        if self.project.coverage is None or self.coverage_alone is None:
            return None
        return self.project.coverage - self.coverage_alone

    @property
    def coverage_uniqueness(self) -> float | None:
        """Calculate percentage of test's coverage that is unique.

        Returns
        -------
        float | None
            Uniqueness percentage (0-100), or None if data unavailable.

        Formula
        -------
        coverage_uniqueness = (coverage_impact / coverage_alone) * 100

        - 100% = All coverage from this test is unique
        - 0% = None of this test's coverage is unique (completely redundant)
        """
        impact = self.coverage_impact
        if impact is None or self.coverage_alone is None or self.coverage_alone == 0:
            return None
        return (impact / self.coverage_alone) * 100

    @property
    def coverage_redundancy(self) -> float | None:
        """Calculate percentage of test's coverage that is redundant.

        Returns
        -------
        float | None
            Redundancy percentage (0-100), or None if data unavailable.

        Formula
        -------
        coverage_redundancy = ((coverage_alone - coverage_impact) / coverage_alone) * 100

        - 0% = Test is completely unique (no redundancy)
        - 100% = Test is completely redundant (all coverage duplicated)
        """
        impact = self.coverage_impact
        if impact is None or self.coverage_alone is None or self.coverage_alone == 0:
            return None
        return ((self.coverage_alone - impact) / self.coverage_alone) * 100

    class Meta:
        indexes = (
            (("project", "file", "suite", "test"), True),
        )  # Unique constraint
