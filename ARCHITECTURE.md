# Yagua Architecture

This document explains the global architecture of Yagua, a tool for collecting and managing test information from pytest-based projects.

## Overview

Yagua follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────┐
│                    CLI Layer                        │
│              (cli.py - CLIManager)                  │
│           Command-line interface & routing          │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│                 Business Logic                      │
│              (project.py - Project)                 │
│        Database management & orchestration          │
└────────┬─────────────────────────────┬──────────────┘
         │                             │
         ▼                             ▼
┌──────────────────────┐    ┌──────────────────────────┐
│   Test Collection    │    │     Data Persistence     │
│  (testsuites/*)      │    │    (models.py - ORM)     │
│  Framework adapters  │    │   Database schema        │
└──────────────────────┘    └──────────────────────────┘
```

## Core Components

### 1. CLI Layer (`cli.py`)

**Purpose**: User interface and command routing

**Key Classes**:
- `CLIManager`: Contains all CLI commands as public methods
  - `create_project()`: Initialize new project cache
  - `collect_tests()`: Collect tests from a project
  - `collect_coverage()`: Run coverage analysis
  - `info()`: Display project information
  - `list_tests()`: Show all tests

**Design Pattern**: Command Pattern with introspection
- Methods are auto-registered as CLI commands via `_create_app()`
- Method names with underscores become hyphenated commands (e.g., `list_tests` → `list-tests`)
- Uses Typer for argument parsing and validation

**Dependencies**:
- `Project` (business logic)
- `PytestSuite` (test collection)

### 2. Business Logic (`project.py`)

**Purpose**: Central orchestrator for project management

**Key Classes**:
- `Project`: Main class managing database connection and operations

**Constructors**:
```python
# Open existing cache
Project(db_path="/path/to/cache.sqlite")

# Create new cache with metadata
Project.from_project_info(
    name="project_name",
    path="/path/to/project",
    description="description",
    db_path="/path/to/cache.sqlite"
)
```

**Key Responsibilities**:
1. **Database Management**:
   - Creates per-project SQLite database instance
   - Manages database lifecycle (connect, transactions, close)
   - Binds ORM models to database at runtime

2. **Test Management**:
   - `collect_tests(suite)`: Orchestrates test collection via suite handlers
   - `add_test()`: Add/update individual test records
   - `get_tests_dataframe()`: Query tests as pandas DataFrame
   - `count_tests()`: Get test count

3. **Coverage Management**:
   - `collect_coverage(suite)`: Run and store coverage data

4. **Project Information**:
   - `store_project_info()`: Update project metadata
   - Magic methods (`__getattr__`, `__dir__`) provide dynamic access to project fields

**Design Patterns**:
- Context Manager: Auto-closes database connection
- Transaction Management: All DB operations wrapped in transactions
- Dynamic Attribute Access: Exposes ProjectModel fields via `__getattr__`

### 3. Test Collection (`testsuites/`)

**Purpose**: Abstract test framework interaction

**Architecture**:
```
testsuites/
├── abc.py           # TestSuiteABC (abstract interface)
└── pytest_suite.py  # PytestSuite (concrete implementation)
```

**Key Classes**:

**`TestSuiteABC`** (Abstract Base Class):
- Defines interface for all test suite handlers
- Abstract methods:
  - `get_tests(project_path)`: Collect test list
  - `get_coverage(project_path, project_name)`: Run coverage

**`PytestSuite`** (Concrete Implementation):
- Implements TestSuiteABC for pytest
- Uses `pytest --collect-only` for test discovery
- Uses `pytest --cov` with JSON output for coverage
- Parses pytest output to extract test information

**Extensibility**:
New test frameworks can be added by implementing TestSuiteABC (e.g., `UnittestSuite`, `NoseSuite`)

### 4. Data Persistence (`models.py`)

**Purpose**: ORM layer for database schema

**Key Models**:

**`ProjectModel`**:
- Singleton pattern (always id=1)
- Fields: `name`, `path`, `description`, `coverage`
- Represents one project per cache file

**`TestModel`**:
- Fields: `project` (FK), `file`, `suite`, `test`, `coverage`
- Unique constraint: `(project, file, suite, test)`
- Currently `coverage` field is unused (project-level only)

**Design Decisions**:
- Uses Peewee ORM for simplicity
- Models are dynamically bound to database at runtime (no global database)
- Each Project instance creates its own database connection

## Data Flow

### Test Collection Flow

```
1. User: yagua collect-tests project.sqlite
         ↓
2. CLI: CLIManager.collect_tests()
   - Validates cache exists
   - Creates Project instance
         ↓
3. Project: collect_tests(suite)
   - Calls suite.get_tests(project_path)
         ↓
4. PytestSuite: get_tests()
   - Runs: pytest --collect-only -q
   - Parses output
   - Returns: [(file, suite, test), ...]
         ↓
5. Project: Iterates test list
   - For each test: add_test(...)
   - Creates/updates TestModel records
         ↓
6. Database: Tests persisted to SQLite
         ↓
7. CLI: Displays summary to user
```

### Coverage Collection Flow

```
1. User: yagua collect-coverage project.sqlite
         ↓
2. CLI: CLIManager.collect_coverage()
         ↓
3. Project: collect_coverage(suite)
   - Calls suite.get_coverage(path, name)
         ↓
4. PytestSuite: get_coverage()
   - Runs: pytest --cov=<name> --cov-report=json
   - Parses JSON output
   - Returns: coverage percentage
         ↓
5. Project: Updates ProjectModel.coverage
         ↓
6. Database: Coverage persisted
         ↓
7. CLI: Displays coverage to user
```

## Architectural Patterns

### 1. Separation of Concerns
- **CLI**: User interface only, no business logic
- **Project**: Business logic and orchestration
- **TestSuites**: Test framework abstraction
- **Models**: Data structure and persistence

### 2. Dependency Injection
- CLI injects suite handlers into Project
- Project doesn't know about concrete suite implementations

### 3. Abstract Factory
- TestSuiteABC defines interface
- Concrete implementations (PytestSuite) provide framework-specific logic
- Easy to add new frameworks without changing Project

### 4. Single Responsibility
- Each class has one clear purpose
- CLI handles user interaction
- Project handles business rules
- Suites handle test framework specifics
- Models handle data structure

### 5. Context Manager
- Project implements `__enter__` and `__exit__`
- Ensures database connections are properly closed
- Provides clean resource management

## Database Architecture

### One Cache Per Project
- Each SQLite file contains exactly one project
- ProjectModel always has id=1 (singleton)
- Simplifies queries and data management
- No need for complex project filtering

### Runtime Binding
- Models are not bound to a global database
- Each Project instance creates its own SqliteDatabase
- Models bound at runtime in `Project.__init__()`
- Enables testing and multiple project instances

### Transaction Management
```python
with project.transaction():
    # All DB operations here
    # Auto-commit on success
    # Auto-rollback on exception
```

## Extension Points

### Adding New Test Frameworks

1. Create new class in `testsuites/`:
```python
from .abc import TestSuiteABC

class UnittestSuite(TestSuiteABC):
    def get_tests(self, project_path):
        # Implement unittest discovery
        pass

    def get_coverage(self, project_path, project_name):
        # Implement unittest coverage
        pass
```

2. Export in `testsuites/__init__.py`:
```python
from .unittest_suite import UnittestSuite
__all__ = ["TestSuiteABC", "PytestSuite", "UnittestSuite"]
```

3. Use in CLI or programmatically:
```python
suite = UnittestSuite()
project.collect_tests(suite)
```

### Adding New CLI Commands

Add method to CLIManager:
```python
def my_command(
    self,
    cache: str = typer.Argument(..., parser=as_path),
) -> None:
    """Command description for help."""
    self._validate_cache_exists(cache)
    with Project(db_path=cache) as proj:
        # Implementation
        pass
```

Auto-registered as: `yagua my-command`

## Design Principles

1. **SOLID Principles**:
   - Single Responsibility: Each class has one job
   - Open/Closed: Extensible via TestSuiteABC without modifying Project
   - Liskov Substitution: Any TestSuiteABC implementation works with Project
   - Interface Segregation: TestSuiteABC has minimal interface
   - Dependency Inversion: Project depends on abstraction (TestSuiteABC), not concrete classes

2. **Clean Architecture**:
   - Business logic (Project) independent of frameworks
   - Database details hidden behind ORM
   - Test frameworks abstracted behind interface

3. **Convention over Configuration**:
   - Automatic CLI command registration
   - NumPy-style docstrings for help text
   - Sensible defaults (cache naming, paths)

## Technology Stack

- **CLI**: Typer (type-safe CLI builder)
- **ORM**: Peewee (lightweight, simple)
- **Database**: SQLite (embedded, zero-config)
- **Data**: Pandas (DataFrame for test listings)
- **Language**: Python 3.10+ (modern type hints)

## Future Enhancements

1. **Per-Test Coverage**:
   - Currently only project-level
   - TestModel.coverage field exists but unused
   - Requires framework-specific implementation

2. **Multiple Test Frameworks**:
   - Add UnittestSuite, NoseSuite
   - Mix multiple frameworks in one project

3. **Historical Data**:
   - Track test changes over time
   - Coverage trends
   - Test execution history

4. **Export Formats**:
   - JSON, CSV, HTML reports
   - Integration with CI/CD tools
