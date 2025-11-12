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

# Collect coverage information
yagua collect-coverage project.sqlite
yagua collect-coverage project.sqlite --force  # Force recalculation

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
        coverage=85.5  # Optional
    )

    # Query tests as DataFrame
    tests_df = proj.get_tests_dataframe()
    print(tests_df)

    # Count tests
    count = proj.count_tests()

    # Collect coverage
    cov = proj.collect_coverage(suite)
    print(f"Coverage: {cov:.2f}%")

    # Access project info via magic methods
    print(f"Project: {proj.name}")
    print(f"Path: {proj.path}")
    print(f"Description: {proj.description}")
    print(f"Coverage: {proj.coverage}")
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
- `coverage` (nullable): Coverage percentage per test (not yet implemented)
- Unique constraint on: `(project, file, suite, test)`

**Note**: Currently, coverage is stored at the project level only. Per-test coverage tracking is planned for future releases.

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
3. The `Project` class handles model binding via `db.bind([BaseModel, ProjectModel, TestModel])`


### Oden de los contenidos en un modulo

1. Documentacion
2. Imports
3. Constantes
4. Globales (siempre privados)
5. Funciones privadas utiles en clases
6. Clases
    0. Variables de clase
    1. Constructor (__init__)
    2. Contructores alternativos (normalmente con los nombres "from_something" y decorados con @classmethod)
    3. Privados ("_name" or "__name")
    4. Propiedades
    5. MEtodos publicos
7. Funciones publicas
