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
  - `create_project()`: Initialize new project work directory with yagua.db
  - `collect_tests()`: Collect tests from a project (with --force option)
  - `collect_coverage()`: Run coverage analysis for project and individual tests (with --force option)
  - `collect_mutations()`: Run mutation testing analysis (with --force option)
  - `info()`: Display project information
  - `list_tests()`: Show all tests (with --long option for full details)

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
# Open existing project
Project(work_dir="/path/to/work_dir")

# Create new project with metadata (creates work_dir/yagua.db)
Project.from_project_info(
    name="project_name",
    path="/path/to/project",
    work_dir="/path/to/work_dir",
    description="description"
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
   - `get_test(test_id)`: Get specific test by test_id (returns TestModel with calculated properties)
   - `count_tests()`: Get test count

3. **Coverage Management**:
   - `collect_coverage(suite)`: Run and store project-level coverage data
   - `collect_coverage_for_test(suite, test_id)`: Run and store coverage for individual test in isolation
   - `collect_coverage_without_test(suite, test_id)`: Run and store coverage excluding a specific test

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
  - `get_tests(project_path)`: Collect test list with pytest node IDs
  - `get_coverage(project_path, project_name)`: Run project-level coverage
  - `get_coverage_for_tests(project_path, project_name, test_ids)`: Run coverage for specific test(s)

**`PytestSuite`** (Concrete Implementation):
- Implements TestSuiteABC for pytest
- Uses `pytest --collect-only` for test discovery
- Uses `pytest --cov` with JSON output for project coverage
- Uses `pytest <test_id1> <test_id2> ... --cov` for running specific test(s) with coverage
- Supports both single test and multiple tests in one execution
- Parses pytest output to extract test information
- Returns command, stdout, stderr, and result for history tracking
- Manages temporary directory for JSON coverage reports

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
- **Database Fields**: `project` (FK), `file`, `suite`, `test`, `test_id`, `coverage_alone`, `coverage_without`
- **Calculated Properties** (auto-computed from stored fields):
  - `coverage_impact`: Unique coverage contribution = `total_coverage - coverage_without`
  - `coverage_overlap`: Coverage shared with other tests = `total_coverage - coverage_alone`
  - `coverage_uniqueness`: % of test's coverage that is unique = `(coverage_impact / coverage_alone) × 100`
  - `coverage_redundancy`: % of test's coverage that is redundant = `((coverage_alone - coverage_impact) / coverage_alone) × 100`
- `test_id`: Unique pytest node ID (e.g., 'test_file.py::TestClass::test_method')
- `coverage_alone`: Coverage when running this test in isolation
- `coverage_without`: Coverage when running all tests except this one
- Unique constraint: `(project, file, suite, test)`

**`HistoryModel`**:
- Fields: `project` (FK), `tag`, `command`, `stdout`, `stderr`, `result`
- `tag`: Command type identifier with test context (e.g., 'collect_tests', 'collect_coverage', 'collect_coverage_for_test::{test_id}', 'collect_coverage_without_test::{test_id}')
- Tracks execution history for all operations with granular test-level tracking

**Design Decisions**:
- Uses Peewee ORM for simplicity
- Models are dynamically bound to database at runtime (no global database)
- Each Project instance creates its own database connection

## Data Flow

### Test Collection Flow

```
1. User: yagua collect-tests my_work_dir
         ↓
2. CLI: CLIManager.collect_tests()
   - Validates work directory exists
   - Creates Project instance
         ↓
3. Project: collect_tests()
   - Uses internal test suite handler
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
6. Database: Tests persisted to work_dir/yagua.db
         ↓
7. CLI: Displays summary to user
```

### Coverage Collection Flow

```
1. User: yagua collect-coverage my_work_dir
         ↓
2. CLI: CLIManager.collect_coverage()
         ↓
3. Project: collect_coverage()
   - Uses internal test suite handler
   - Calls suite.get_coverage(path, name)
         ↓
4. PytestSuite: get_coverage()
   - Runs: pytest --cov=<name> --cov-report=json
   - Parses JSON output
   - Returns: coverage percentage
         ↓
5. Project: Updates ProjectModel.coverage
   - Stores execution history in HistoryModel
         ↓
6. For each test (coverage_alone):
   Project: collect_coverage_for_test(test_id)
   - Calls suite.get_coverage_for_tests(path, name, [test_id])
   - Updates TestModel.coverage_alone
   - Stores execution history in HistoryModel with tag 'collect_coverage_for_test::{test_id}'
         ↓
7. For each test (coverage_without):
   Project: collect_coverage_without_test(test_id)
   - Queries all test IDs except the target test
   - Calls suite.get_coverage_for_tests(path, name, all_other_test_ids)
   - Updates TestModel.coverage_without
   - Stores execution history in HistoryModel with tag 'collect_coverage_without_test::{test_id}'
         ↓
8. Database: All coverage data persisted in work_dir/yagua.db (project, alone, without)
         ↓
9. CLI: Displays coverage summary with hierarchical output per test [X/N]
```

## Architectural Patterns

### 1. Separation of Concerns
- **CLI**: User interface only, no business logic
- **Project**: Business logic and orchestration
- **TestSuites**: Test framework abstraction
- **Models**: Data structure and persistence

### 2. Dependency Injection
- Project manages internal suite handlers
- Suite handlers abstracted behind interfaces (TestSuiteABC, MutationSuiteABC)

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

### One Work Directory Per Project
- Each work directory contains yagua.db with exactly one project
- ProjectModel always has id=1 (singleton)
- All temporary files stored in the same work directory
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
project._init_suite(test_suite=suite)
project.collect_tests()
```

### Adding New CLI Commands

Add method to CLIManager:
```python
def my_command(
    self,
    work_dir: str = _make_work_dir_argument(),
) -> None:
    """Command description for help."""
    with self._use_project(work_dir) as proj:
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

1. **Performance Optimization**:
   - Cache test execution results to avoid redundant runs
   - Parallel execution of coverage collection for multiple tests
   - Incremental coverage updates for modified tests only

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
