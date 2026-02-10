"""Yagua - Database Models.

This module defines the Peewee ORM models for the yagua project database.
Each work directory contains exactly one project database with its associated
tests and command history. Models are dynamically bound to database instances
at runtime.

Models
------
BaseModel : class
    Abstract base class providing timestamp fields and utility methods.
ProjectModel : class
    Stores project metadata (limited to one row per database).
TestModel : class
    Stores individual test information and coverage metrics.
HistoryModel : class
    Stores command execution history for audit purposes.

Database Design
---------------
- One SQLite file = One project
- Each project can have many tests
- Each project can have many history entries
- All timestamps are stored in UTC
- Models are bound to database instances in ProjectStore.__init__()

Notes
-----
Models in this module do not have a hardcoded database connection.
The database binding happens dynamically in the ProjectStore class using
Peewee's bind_ctx() context manager, allowing multiple ProjectStore
instances to each have their own database connection.
"""

from datetime import datetime, timezone

import numpy as np

from peewee import (
    Model,
    CharField,
    FloatField,
    ForeignKeyField,
    Check,
    DateTimeField,
    TextField,
    IntegerField,
)
from playhouse import hybrid


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

    @classmethod
    def _fields(cls):
        """Get list of field names defined in the model.

        Returns
        -------
        list[str]
            List of field names in the order they are defined.
        """
        return [field.name for field in cls._meta.sorted_fields]

    @classmethod
    def _hproperties(cls):
        """Get list of hybrid property names defined in the model.

        Hybrid properties are computed attributes that can be accessed
        both at the instance level and in database queries.

        Returns
        -------
        list[str]
            Sorted list of hybrid property names (excludes private properties).
        """
        props = []
        for k, v in vars(cls).items():
            if k.startswith("_"):
                continue
            if isinstance(v, hybrid.hybrid_property):
                props.append(k)
        props.sort()
        return props

    def save(self, *args, **kwargs):
        """Save model instance and update modified_at timestamp.

        This method overrides the default save() to automatically update
        the modified_at field to the current UTC time on every save.

        Parameters
        ----------
        *args
            Positional arguments passed to parent save().
        **kwargs
            Keyword arguments passed to parent save().

        Returns
        -------
        int
            Number of rows modified (typically 1).
        """
        self.modified_at = datetime.now(timezone.utc)
        return super().save(*args, **kwargs)

    def to_records(self):
        """Convert model instance to list of (field_name, value) tuples.

        This method includes both regular fields and hybrid properties,
        making it useful for converting model data to formats like
        DataFrames or dictionaries.

        Returns
        -------
        list[tuple[str, Any]]
            List of tuples containing (field_name, field_value) for all
            fields and hybrid properties in the model.

        Examples
        --------
        >>> test = TestModel.get_by_id(1)
        >>> records = test.to_records()
        >>> dict(records)
        {'id': 1, 'file': 'test_foo.py', 'coverage_alone': 45.5, ...}
        """
        data = []
        fields = self._fields() + self._hproperties()
        for field in fields:
            data.append((field, getattr(self, field)))
        return data


class ProjectModel(BaseModel):
    """Project information table.

    This table is limited to a single row per database.
    Each work directory represents exactly one project.
    The id must always be 1.

    Attributes
    ----------
    name : CharField
        Project name or identifier.
    path : CharField
        Filesystem path to the project directory.
    work_path : CharField
        Working directory for yagua operations (coverage, mutations, etc.).
        Created automatically if not provided, defaults to
        _yagua_wd_<project_name>_ in the current directory.
    description : CharField, optional
        Optional project description.
    mutation_timeout : FloatField, optional
        Timeout in seconds for mutation testing execution.
        None means no timeout (use mutation suite's default).
    coverage : FloatField, optional
        Total project coverage percentage (0-100).
        Updated via collect-coverage command.
    mutants_number : IntegerField, optional
        Total number of mutants generated for the project.
        Updated via collect-mutations command.
    msr : FloatField, optional
        Mutation Survival Ratio for the entire project (0-100).
        Represents the percentage of mutants that survived (were not killed).
        Lower values indicate more effective test suites.
        Note: mutation_score = 100 - msr
        Updated via collect-mutations command.
    pipeline_step : CharField
        Current step in the analysis pipeline. One of:
        'created', 'tests_collected', 'coverage_collected',
        'mutations_collected'.
        Used for resumability and progress tracking.
    failed_at : DateTimeField, optional
        UTC timestamp of last pipeline failure, if any.
        None if pipeline has not failed.

    Hybrid Properties
    -----------------
    mutants_survived : int | None
        Number of mutants that survived the full test suite.
        Calculated from msr and mutants_number.
    mutants_killed : int | None
        Number of mutants killed by the full test suite.
        Calculated as: mutants_number - mutants_survived

    Notes
    -----
    The Check constraint ensures only one row (id=1) can exist per database,
    enforcing the one-project-per-cache-file design.

    """

    name = CharField()
    path = CharField()
    work_path = CharField()
    test_suite_name = CharField()
    mutation_suite_name = CharField()
    description = CharField(null=True)
    mutation_timeout = FloatField(null=True, default=None)

    coverage = FloatField(null=True, default=None)

    mutants_number = IntegerField(null=True, default=None)
    msr = FloatField(null=True, default=None)

    # Pipeline state tracking
    pipeline_step = CharField(default="created")
    failed_at = DateTimeField(null=True, default=None)

    @hybrid.hybrid_property
    def mutants_survived(self):
        """Calculate the number of mutants that survived the full test suite.

        Returns
        -------
        int | None
            Number of surviving mutants, or None if mutation data unavailable.

        Formula
        -------
        mutants_survived = round(msr * mutants_number )

        """
        try:
            the_ms = self.msr * self.mutants_number
            return int(round(the_ms))
        except TypeError:
            return None

    @hybrid.hybrid_property
    def mutants_killed(self):
        """Calculate the number of mutants killed by the full test suite.

        Returns
        -------
        int | None
            Number of killed mutants, or None if mutation data unavailable.

        Formula
        -------
        mutants_killed = mutants_number - mutants_survived

        """
        try:
            return self.mutants_number - self.mutants_survived
        except TypeError:
            return None

    class Meta:
        # Ensure only one project per database
        # The id must always be 1
        constraints = [Check("id = 1")]
        table_name = "yagua_project"


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
    msr_alone : FloatField, optional
        Mutation Survival Ratio when running only this test in isolation (0-100).
        Represents the percentage of mutants that survived when tested alone.
        Lower values indicate this test is more effective at killing mutants.
        Updated via collect-mutations command with per-test analysis.
    msr_without : FloatField, optional
        Mutation Survival Ratio when running all tests except this one (0-100).
        Represents the percentage of mutants that survived without this test.
        Updated via collect-mutations command, useful for identifying
        which mutants are uniquely detected by this test.

    Hybrid Properties
    -----------------
    coverage_impact : float | None
        Unique coverage contribution of this test.
        Calculated as: total_coverage - coverage_without
    coverage_uniqueness : float | None
        Percentage of this test's coverage that is unique (0-100).
        Calculated as: (coverage_impact / coverage_alone) × 100
    mutants_survived_alone : int | None
        Number of mutants that survived when running only this test.
        Calculated from msr_alone and project.mutants_number.
    mutants_killed_alone : int | None
        Number of mutants killed when running only this test.
        Calculated as: mutants_number - mutants_survived_alone
    mutants_survived_without : int | None
        Number of mutants that survived when running all tests except this one.
        Calculated from msr_without and project.mutants_number.
    mutants_killed_without : int | None
        Number of mutants killed when running all tests except this one.
        Calculated as: mutants_number - mutants_survived_without
    information_weights : float
        Normalized weight of this test's mutation impact (0-1).
        Used in entropy calculations for macrostate tightness index.
        Calculated as: mutants_killed_alone / sum(all mutants_killed_alone)

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

    # Coverage
    coverage_alone = FloatField(null=True, default=None)
    coverage_without = FloatField(null=True, default=None)

    # Mutations
    msr_alone = FloatField(null=True, default=None)
    msr_without = FloatField(null=True, default=None)

    @hybrid.hybrid_property
    def coverage_impact(self):
        """Calculate the unique coverage contribution of this test.

        This metric measures how much coverage would be lost if this test
        were removed from the suite. It represents the coverage that is
        exclusively provided by this test.

        Returns
        -------
        float | None
            Coverage impact (0-100), or None if coverage data unavailable.

        Formula
        -------
        coverage_impact = total_coverage - coverage_without

        """
        try:
            return self.project.coverage - self.coverage_without
        except TypeError:
            return None

    @hybrid.hybrid_property
    def coverage_uniqueness(self):
        """Calculate the percentage of this test's coverage that is unique.

        This metric measures how much of this test's coverage is not
        duplicated by other tests in the suite. A high uniqueness
        percentage indicates this test covers code that other tests miss.

        Returns
        -------
        float | None
            Coverage uniqueness percentage (0-100), or None if coverage
            data is unavailable or coverage_alone is zero.

        Formula
        -------
        coverage_uniqueness = (coverage_impact / coverage_alone) × 100

        """
        try:
            return (self.coverage_impact / self.coverage_alone) * 100.0
        except (TypeError, ZeroDivisionError):
            return None

    @hybrid.hybrid_property
    def mutants_survived_alone(self):
        """Calculate number of mutants that survived when running only this test.

        Returns
        -------
        int | None
            Number of surviving mutants, or None if mutation data unavailable.

        Formula
        -------
        mutants_survived_alone = round(msr_alone * mutants_number )

        """
        try:
            the_ms_alone = self.msr_alone * self.project.mutants_number
            return int(round(the_ms_alone))
        except TypeError:
            return None

    @hybrid.hybrid_property
    def mutants_killed_alone(self):
        """Calculate number of mutants killed when running only this test.

        Returns
        -------
        int | None
            Number of killed mutants, or None if mutation data unavailable.

        Formula
        -------
        mutants_killed_alone = mutants_number - mutants_survived_alone

        """
        try:
            return self.project.mutants_number - self.mutants_survived_alone
        except TypeError:
            return None

    @hybrid.hybrid_property
    def mutants_survived_without(self):
        """Calculate mutants that survived when running all tests except this one.

        Returns
        -------
        int | None
            Number of surviving mutants, or None if mutation data unavailable.

        Formula
        -------
        mutants_survived_without = round(msr_without * mutants_number )

        """
        try:
            the_ms_without = self.msr_without * self.project.mutants_number
            return int(round(the_ms_without))
        except TypeError:
            return None

    @hybrid.hybrid_property
    def mutants_killed_without(self):
        """Calculate mutants killed when running all tests except this one.

        Returns
        -------
        int | None
            Number of killed mutants, or None if mutation data unavailable.

        Formula
        -------
        mutants_killed_without = mutants_number - mutants_survived_without

        """
        try:
            return self.project.mutants_number - self.mutants_survived_without
        except TypeError:
            return None

    @hybrid.hybrid_property
    def information_weights(self):
        """Calculate the normalized weight of this test's mutation impact.

        This metric represents the relative contribution of this test to
        the total mutation-killing capability of the test suite. It is used
        in entropy-based calculations like the Macrostate Tightness Index.

        Returns
        -------
        float
            Normalized weight between 0 and 1, where:
            - Higher values: test kills more mutants relative to other tests
            - Lower values: test kills fewer mutants relative to other tests
            - Sum of all weights across all tests equals 1.0

        Formula
        -------
        w_i = mutants_killed_alone_i / sum(mutants_killed_alone_j for all j)

        Notes
        -----
        - Used for computing Shannon entropy in macrostate_tightness_ratio
        - Requires mutation testing data to be collected
        - Tests that kill no mutants have weight 0

        See Also
        --------
        ProjectStore.macrostate_tightness_ratio : Uses these weights for MTI

        """
        try:
            all_tests = list(self.project.tests)
            denom = np.sum([t.mutants_killed_alone for t in all_tests])

            return self.mutants_killed_alone / denom
        except TypeError:
            return None

    class Meta:
        table_name = "yagua_tests"
        indexes = ((("project", "file", "suite", "test"), True),)


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
    status_code : IntegerField
        Exit status code from the command execution.
    stdout : TextField
        Standard output from the command execution.
    stderr : TextField
        Standard error output from the command execution.
    result : TextField
        Additional result data from the command execution.
        Can store JSON data or other structured information.
    """

    project = ForeignKeyField(ProjectModel, backref="history")
    tag = CharField()
    command = TextField()
    status_code = IntegerField()
    stdout = TextField()
    stderr = TextField()
    result = TextField()

    class Meta:
        table_name = "yagua_histories"
