# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Rules

**NEVER perform `git push` without explicit permission from the user.**

When creating commits, ALWAYS ask the user if they want to push the changes to the remote repository. Never assume that push is desired.

## Project Overview

This repository contains **yagua**, a Python package for collecting and managing test information from pytest-based projects, along with:
- **External projects**: Git submodules (like `astroalign`) managed via `update_projects.py` for testing and research

The working directory is `/home/juanbc/proyectos/yagua/src`.

## yagua Package Architecture

The `yagua` package is structured as follows:

```
yagua/
├── __init__.py         # Exposes: main, Project, PytestSuite, TestSuiteABC
├── models.py           # Peewee ORM models (ProjectModel, TestModel, HistoryModel)
├── project.py          # Project class - database management
├── cli.py              # Typer CLI commands and application setup
└── testsuites/
    ├── __init__.py     # Test suite handlers module
    ├── abc.py          # TestSuiteABC abstract base class
    └── pytest_suite.py # PytestSuite implementation
```

### Key Architectural Patterns

**One Cache File Per Project**
- Each cache file represents a single project
- The project is automatically created/updated in the database when instantiating `Project`
- Each `Project` instance creates its own Peewee `SqliteDatabase` connection
- Models are dynamically bound to the database instance in `Project.__init__()`
- The database instance lives in the `Project` class, not as a global singleton

**Two Constructor Patterns**
```python
# Direct constructor - opens existing cache file
project = Project(db_path="/path/to/cache.sqlite")

# Alternative constructor - creates new cache with project info
project = Project.from_project_info(
    name="my_project",
    path="/path/to/project",
    description="Optional description",
    db_path="/path/to/cache.sqlite"  # Must not exist
)
```

**CLI Command Registration**
- CLI commands are class methods in `CLIManager`
- Commands are auto-registered via introspection in `_create_app()`
- Method names with underscores (e.g., `list_tests`) become hyphenated commands (`list-tests`)
- Each command receives cache path as argument (not via context)

**Test Suite Handlers**
- Test collection is separated into dedicated suite handler classes
- `PytestSuite`: Handles pytest-based project test discovery and collection
- Suite handlers are responsible for discovering tests and optionally saving them to a project
- The pattern allows easy extension for other test frameworks (unittest, nose, etc.)

## Installation

### Development Installation

```bash
# Install in editable mode with all dependencies
pip install -e .

# Install with development dependencies
pip install -e ".[dev]"
```

After installation, the `yagua` command will be available globally.

## Common Commands

### Running yagua CLI

```bash
# Show help
yagua --help

# Create a new project cache
yagua create-project /path/to/project
yagua create-project /path/to/project my_cache.sqlite --name "My Project" --description "Description"

# Collect tests from a project
yagua collect-tests project.sqlite

# Show project information
yagua info project.sqlite

# List tests for a project
yagua list-tests project.sqlite
yagua list-tests project.sqlite --long  # Show all columns including timestamps and IDs
yagua list-tests project.sqlite -l      # Short form

# Collect coverage information
yagua collect-coverage project.sqlite
yagua collect-coverage project.sqlite --force  # Force recalculation of all coverage

# Force recollection of tests
yagua collect-tests project.sqlite --force
yagua collect-tests project.sqlite -f  # Short form

# Alternatively, using Python module
python -m yagua <command>
```

### Managing External Projects

```bash
# Update/clone all projects listed in PROJECTS
python update_projects.py
```

### Working with Projects Programmatically

```python
from yagua import Project, PytestSuite

# Create a new project with metadata
proj = Project.from_project_info(
    name="my_project",
    path="/path/to/project",
    description="Optional description",
    db_path="qa.sqlite"
)

# Use as context manager (auto-closes database)
with Project(db_path="qa.sqlite") as proj:
    # Collect and save tests from a pytest suite
    suite = PytestSuite()
    saved_count, updated_count = proj.collect_tests(suite)
    print(f"Saved {saved_count} new tests, updated {updated_count}")

    # Add individual test
    project_model = proj._get_project_model()
    test, created = proj.add_test(
        project=project_model,
        file="test_file.py",
        suite="TestSuite",  # Can be None
        test="test_example",
    )

    # Query tests as DataFrame
    tests_df = proj.get_tests_dataframe()
    print(tests_df)

    # Count tests
    count = proj.count_tests()

    # Collect coverage for all tests
    cov = proj.collect_coverage(suite)
    print(f"Coverage: {cov:.2f}%")

    # Collect coverage for individual test
    test_id = "test_file.py::test_example"
    test_cov = proj.collect_coverage_for_test(suite, test_id)
    print(f"Coverage for {test_id}: {test_cov:.2f}%")

    # Access project info via properties
    print(f"Project: {proj.name}")
    print(f"Path: {proj.path}")
    print(f"Description: {proj.description}")
    print(f"Coverage: {proj.coverage}")
```

## Database Schema

All models inherit from `BaseModel` which provides:
- `created_at`: UTC timestamp when record was created (auto-set)
- `modified_at`: UTC timestamp when record was last modified (auto-updated)

**ProjectModel**
- Limited to a single row per database (id=1)
- `name`: Project identifier
- `path`: Filesystem path to project
- `description` (nullable): Optional description
- `coverage` (nullable): Total project coverage percentage

**TestModel**
- `project` (FK): Reference to ProjectModel (always id=1)
- `file`: Test file path
- `suite` (nullable): Test suite/class name
- `test`: Test function name
- `test_id`: Unique pytest node ID for the test (e.g., 'test_file.py::TestClass::test_method')
- `coverage_alone` (nullable): Coverage when running test in isolation
- `coverage_without` (nullable): Coverage when running all tests except this one (not yet implemented)
- Unique constraint on: `(project, file, suite, test)`

**HistoryModel**
- `project` (FK): Reference to ProjectModel (always id=1)
- `tag`: Command type identifier (e.g., 'collect_tests', 'collect_coverage', 'collect_coverage_for_test')
- `command`: Full command string executed (e.g., 'pytest --collect-only -q')
- `stdout`: Standard output from command execution
- `stderr`: Standard error from command execution
- `result`: Additional result data (e.g., raw output, JSON data)

## Development Notes

### Adding New CLI Commands

Add a new method to `CLIManager` in `cli.py`:
```python
def my_command(
    self,
    cache: str = typer.Argument(
        ...,
        help="Path to SQLite cache file",
        parser=as_path,
    ),
    my_option: str = typer.Option(
        None,
        "--my-option",
        help="Description of option"
    ),
) -> None:
    """Command description for help text.

    This docstring summary will be used as the command help text.
    Everything before the first section separator is extracted.

    Parameters
    ----------
    cache : Path
        Path to cache file.
    my_option : str, optional
        Description of option.
    """
    self._validate_cache_exists(cache)

    with Project(db_path=cache) as proj:
        # Implementation
        pass
```

The command will be auto-registered as `my-command`. Use NumPy-style docstrings for consistency.

### Modifying Database Models

1. Update models in `models.py`
2. Since Peewee models are bound at runtime in `Project.__init__()`, ensure `BaseModel` has no hardcoded database
3. The `Project` class handles model binding via `db.bind([BaseModel, ProjectModel, TestModel, HistoryModel])`
4. Update `MODELS_TO_CREATE` constant in `project.py` if adding new models


### Module Content Organization

Code should be organized in the following order:

1. Documentation (module docstring)
2. Imports
3. Constants
4. Globals (always private)
5. Private helper functions (used by classes)
6. Classes
    - Class variables
    - Constructor (`__init__`)
    - Alternative constructors (typically named `from_something` and decorated with `@classmethod`)
    - Private methods (`_name` or `__name`)
    - Properties (decorated with `@property`)
    - Public methods
7. Public functions
