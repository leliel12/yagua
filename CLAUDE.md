# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains **qa_entropy**, a research/testing workspace that includes:
- **yagua**: A Python package for collecting and managing test information from pytest-based projects
- **External projects**: Git submodules (like `astroalign`) managed via `update_projects.py`

The working directory is `/home/juanbc/proyectos/qa_entropy/src`.

## yagua Package Architecture

The `yagua` package is structured as follows:

```
yagua/
├── __init__.py         # Exposes: main, Project, PytestSuite
├── models.py           # Peewee ORM models (ProjectModel, TestModel)
├── project.py          # Project class - database management
├── cli.py              # Typer CLI commands and application setup
├── utils.py            # Deprecated utility functions
└── testsuites/
    ├── __init__.py     # Test suite handlers module
    └── pytest_suite.py # PytestSuite class
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
# Direct constructor - receives project details and cache path
project = Project(
    cache_path="/path/to/cache.sqlite",
    name="my_project",
    path="/path/to/project",
    description="Optional description"
)

# Alternative constructor - receives project path and derives name from directory
project = Project.from_path(
    project_path="/path/to/project",
    cache_path="/path/to/cache.sqlite",
    description="Optional description"
)
```

**CLI Command Registration**
- CLI commands are class methods in `CLIManager`
- Commands are auto-registered via introspection in `_create_app()`
- Method names with underscores (e.g., `list_tests`) become hyphenated commands (`list-tests`)
- All methods receive `typer.Context` as first parameter containing `cache_path`

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
# Using installed command
yagua --cache /path/to/cache.sqlite <command>

# Collect tests from a project
yagua --cache qa.sqlite collect /path/to/project

# Collect tests with custom name and description
yagua --cache qa.sqlite collect /path/to/project --name "my_project" --description "My project description"

# Show project information
yagua --cache qa.sqlite info /path/to/project

# List tests for a project
yagua --cache qa.sqlite list-tests /path/to/project

# Alternatively, using Python module
python -m yagua --cache qa.sqlite <command>
```

### Managing External Projects

```bash
# Update/clone all projects listed in PROJECTS
python update_projects.py
```

### Working with Projects Programmatically

```python
from yagua import Project, PytestSuite

# Use as context manager (auto-closes database)
# Project is automatically created/updated in the database
with Project(
    cache_path="qa.sqlite",
    name="my_project",
    path="/path/to/project",
    description="Optional description"
) as proj:
    # Collect and save tests from a pytest suite
    suite = PytestSuite("/path/to/project")
    saved_count, updated_count = proj.collect_tests(suite)
    print(f"Saved {saved_count} new tests, updated {updated_count}")

    # Or collect tests manually
    tests_found = suite.collect_tests()
    for file, suite_name, test in tests_found:
        proj.add_test(file=file, suite=suite_name, test=test)

    # Add individual test
    test, created = proj.add_test(
        file="test_file.py",
        suite="TestSuite",  # Can be None
        test="test_example",
        coverage=85.5  # Optional
    )

    # Query tests
    tests = proj.list_tests()

    # Access project info
    print(f"Project: {proj.project.name}")
    print(f"Path: {proj.project.path}")

# Alternative: Use from_path constructor
with Project.from_path(
    project_path="/path/to/project",
    cache_path="qa.sqlite",
    description="Optional description"
) as proj:
    # The project name is derived from the directory name
    suite = PytestSuite("/path/to/project")
    proj.collect_tests(suite)
```

## Database Schema

**ProjectModel**
- Limited to a single row per database (id=1)
- `name`: Project identifier
- `path`: Filesystem path to project
- `description` (nullable): Optional description

**TestModel**
- `project` (FK): Reference to ProjectModel (always id=1)
- `file`: Test file path
- `suite` (nullable): Test suite/class name
- `test`: Test function name
- `coverage` (nullable): Coverage percentage
- Unique constraint on: `(project, file, suite, test)`

## Development Notes

### Adding New CLI Commands

Add a new method to `CLIManager` in `cli.py`:
```python
def my_command(
    self,
    ctx: typer.Context,
    project_path: str = typer.Argument(..., help="Path to project"),
) -> None:
    """Command description for help text."""
    cache_path = ctx.obj.cache_path
    project_path_obj = Path(project_path).resolve()

    with Project(
        cache_path=cache_path,
        name=project_path_obj.name,
        path=str(project_path_obj),
    ) as proj:
        # Implementation
        pass
```

The command will be auto-registered as `my-command`.

### Modifying Database Models

1. Update models in `models.py`
2. Since Peewee models are bound at runtime in `Project.__init__()`, ensure `BaseModel` has no hardcoded database
3. The `Project` class handles model binding via `db.bind([BaseModel, ProjectModel, TestModel])`
