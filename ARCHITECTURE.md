# Yagua Architecture

This document explains the global architecture of Yagua, a tool for collecting and managing test information from pytest-based projects.

## Overview

Yagua follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Layer                               │
│                   (cli.py - CLIManager)                         │
│          Command routing & session-based pipeline               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                         │
│              (project_manager.py - ProjectManager)              │
│         Pipeline validation, state tracking, workflows          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Data Access Layer                             │
│                  (project.py - Project)                         │
│           Database operations & suite orchestration             │
└────────┬──────────────────┬──────────────────┬──────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
┌────────────────┐  ┌────────────────┐  ┌──────────────────────┐
│ Test Suites    │  │ Mutation Suite │  │  Data Persistence    │
│ (testsuites/*) │  │(mutationsuites)│  │  (models.py - ORM)   │
│ subprocess-    │  │ subprocess-    │  │  Database schema     │
│ based adapters │  │ based adapters │  │                      │
└────────────────┘  └────────────────┘  └──────────────────────┘
```

## Core Components

### 1. CLI Layer (`cli.py`)

**Purpose**: User interface and command routing

**Key Classes**:
- `CLIManager`: Contains all CLI commands as public methods
  - `init()`: Initialize new project work directory with yagua.db
  - `run()`: Execute complete pipeline (tests, coverage, mutations) with --rerun/-r option
  - `status()`: Display pipeline execution status
  - `report()`: Show comprehensive results report
  - `export()`: Export project data to archive file

**Design Pattern**: Command Pattern with session-based pipeline
- Methods are auto-registered as CLI commands via `_create_app()`
- Method names with underscores become hyphenated commands
- Uses Typer for argument parsing and validation
- Pipeline pattern with state tracking and resumability

**Dependencies**:
- `ProjectManager` (business logic with pipeline validation)
- `Project` (database access layer)

### 2. Business Logic (`project.py` and `project_manager.py`)

**Purpose**: Layered architecture for project management

**Key Classes**:

**`Project` (Database Access Layer)**:
- Manages database connection and low-level operations

**Constructors**:
```python
# Open existing project
Project(work_dir="/path/to/work_dir")

# Create new project with metadata (creates work_dir/yagua.db)
Project.from_project_info(
    name="project_name",
    path="/path/to/project",
    work_dir="/path/to/work_dir",
    description="description",
    mutation_timeout=50.0
)
```

**Key Responsibilities**:
1. **Database Management**:
   - Creates per-project SQLite database instance
   - Manages database lifecycle (connect, transactions, close)
   - Binds ORM models to database at runtime

2. **Test Management**:
   - `collect_tests()`: Orchestrates test collection via suite handlers
   - `add_test()`: Add/update individual test records
   - `get_tests_dataframe()`: Query tests as pandas DataFrame
   - `get_test(test_id)`: Get specific test by test_id (returns TestModel)
   - `count_tests()`: Get test count

3. **Coverage Management**:
   - `collect_coverage()`: Run and store project-level coverage data
   - `collect_coverage_for_test(test_id)`: Run and store coverage for individual test
   - `collect_coverage_without_test(test_id)`: Run and store coverage excluding a test

4. **Mutation Management**:
   - `collect_mutations()`: Run and store mutation testing data
   - `collect_mutations_for_test(test_id)`: Run mutations for individual test
   - `collect_mutations_without_test(test_id)`: Run mutations excluding a test

5. **Project Information**:
   - `store_project_info()`: Update project metadata
   - Magic methods (`__getattr__`, `__dir__`) provide dynamic access to project fields

**`ProjectManager` (Business Logic Layer)**:
- Wraps Project to provide pipeline validation and workflow management
- `run_pipeline()`: Executes complete pipeline with state tracking
- `get_pipeline_status()`: Returns execution status for each stage
- Validates pipeline dependencies and resumability

**Design Patterns**:
- Context Manager: Auto-closes database connection
- Transaction Management: All DB operations wrapped in transactions
- Dynamic Attribute Access: Exposes ProjectModel fields via `__getattr__`
- Layered Architecture: DAL (Project) + Business Logic (ProjectManager)

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
- Implements TestSuiteABC for pytest using subprocess
- Uses subprocess.run() for executing pytest as external command
- Uses `pytest --collect-only` for test discovery
- Uses `pytest --cov` with JSON output for project coverage
- Uses `pytest <test_id1> <test_id2> ... --cov` for specific test(s) with coverage
- Hash-based temporary file naming for deterministic identification
- Supports both single test and multiple tests in one execution
- Parses pytest output to extract test information
- Returns command, stdout, stderr, and result for history tracking

**Extensibility**:
New test frameworks can be added by implementing TestSuiteABC (e.g., `UnittestSuite`, `NoseSuite`)

### 4. Mutation Collection (`mutationsuites/`)

**Purpose**: Abstract mutation testing framework interaction

**Architecture**:
```
mutationsuites/
├── abc.py                  # MutationSuiteABC (abstract interface)
└── cosmicray_suite.py      # CosmicRaySuite (concrete implementation)
```

**Key Classes**:

**`MutationSuiteABC`** (Abstract Base Class):
- Defines interface for all mutation suite handlers
- Abstract methods:
  - `get_mutants(project_path, project_name, force)`: Count total mutants
  - `get_survival_rate(project_path, project_name, force)`: Run full mutation testing
  - `get_survival_rate_for_tests(project_path, project_name, test_ids, force)`: Run mutations for specific test(s)

**`CosmicRaySuite`** (Concrete Implementation):
- Implements MutationSuiteABC for cosmic-ray using subprocess
- Uses subprocess.run() for executing cosmic-ray CLI commands
- Uses `cosmic-ray init` for session initialization
- Uses `cosmic-ray exec` for mutation execution
- Uses `cr-xml` for getting mutant count
- Uses `cr-rate` for calculating survival rate
- Manual TOML configuration writing for better isolation
- Hash-based session file naming for deterministic identification
- Respects mutation_timeout parameter from project configuration
- Returns command, stdout, stderr, and result for history tracking

**Extensibility**:
New mutation frameworks can be added by implementing MutationSuiteABC (e.g., `MutmutSuite`, `PITSuite`)

### 5. Data Persistence (`models.py`)

**Purpose**: ORM layer for database schema

**Key Models**:

**`ProjectModel`**:
- Singleton pattern (always id=1)
- **Fields**:
  - `name`: Project name or identifier
  - `path`: Filesystem path to the project directory
  - `work_path`: Working directory for yagua operations
  - `test_suite_name`: Name of the test suite implementation being used
  - `mutation_suite_name`: Name of the mutation suite implementation being used
  - `description`: Optional project description (nullable)
  - `coverage`: Total project coverage percentage (nullable)
  - `mutants_number`: Total number of mutants generated (nullable)
  - `msr`: Mutation Score Ratio for the entire project (nullable)
- Represents one project per work directory

**`TestModel`**:
- **Database Fields**:
  - `project`: Foreign key to ProjectModel
  - `test_id`: Unique pytest node ID (e.g., 'test_file.py::TestClass::test_method')
  - `file`: Test file path
  - `suite`: Test suite/class name (nullable)
  - `test`: Test function name
  - `coverage_alone`: Coverage when running this test in isolation (nullable)
  - `coverage_without`: Coverage when running all tests except this one (nullable)
  - `msr_alone`: Mutation Score Ratio for this test alone (nullable)
  - `msr_without`: Mutation Score Ratio without this test (nullable)
- **Calculated Properties** (auto-computed hybrid properties):
  - **Coverage Metrics**:
    - `coverage_impact`: Unique coverage contribution = `total_coverage - coverage_without`
    - `coverage_overlap`: Coverage shared with other tests = `coverage_without + coverage_alone - total_coverage`
    - `coverage_uniqueness`: % of test's coverage that is unique = `(coverage_impact / coverage_alone) × 100`
    - `coverage_redundancy`: % of test's coverage that is redundant = `((coverage_alone - coverage_impact) / coverage_alone) × 100`
  - **Mutation Testing Metrics**:
    - `msr_impact`: Unique MSR contribution = `total_msr - msr_without`
    - `msr_overlap`: Mutants killed redundantly with other tests = `msr_without + msr_alone - total_msr`
    - `msr_uniqueness`: % of test's killed mutants that are unique = `(msr_impact / msr_alone) × 100`
    - `msr_redundancy`: % of test's killed mutants that are redundant = `((msr_alone - msr_impact) / msr_alone) × 100`
- **Constraints**:
  - Unique constraint on `test_id` field
  - Unique constraint on `(project, file, suite, test)` tuple

**`HistoryModel`**:
- **Fields**:
  - `project`: Foreign key to ProjectModel
  - `tag`: Command type identifier with test context (e.g., 'collect_tests', 'collect_coverage', 'collect_coverage_for_test::{test_id}', 'collect_coverage_without_test::{test_id}')
  - `command`: The full command string that was executed
  - `status_code`: Exit code from command execution
  - `stdout`: Standard output from the command execution
  - `stderr`: Standard error output from the command execution
  - `result`: Additional result data (can store JSON or other structured information)
- Tracks execution history for all operations with granular test-level tracking

**Design Decisions**:
- Uses Peewee ORM for simplicity
- Models are dynamically bound to database at runtime (no global database)
- Each Project instance creates its own database connection

## Data Flow

### Pipeline Execution Flow

```
1. User: yagua run my_work_dir
         ↓
2. CLI: CLIManager.run()
   - Opens project via read_dir() (returns ProjectManager)
   - Calls ProjectManager.run_pipeline()
         ↓
3. ProjectManager: run_pipeline()
   - Checks pipeline status (resumability)
   - Executes stages in order:
     a) Test collection (if not done or rerun=True)
     b) Coverage collection (if not done or rerun=True)
     c) Mutation collection (if not done or rerun=True)
         ↓
4a. Test Collection Stage:
    Project: collect_tests()
    - Uses internal test suite handler (PytestSuite)
    - Calls suite.get_tests(project_path)
    - PytestSuite runs: pytest --collect-only -q (via subprocess)
    - Parses output and returns test list
    - Creates/updates TestModel records
    - Stores execution history in HistoryModel
         ↓
4b. Coverage Collection Stage:
    Project: collect_coverage()
    - Calls suite.get_coverage() for total coverage
    - PytestSuite runs: pytest --cov=<name> --cov-report=json (via subprocess)
    - Updates ProjectModel.coverage
    - For each test:
      * collect_coverage_for_test(): runs test alone
      * collect_coverage_without_test(): runs all tests except one
    - Updates TestModel.coverage_alone and coverage_without
    - Calculated properties auto-computed (impact, overlap, uniqueness, redundancy)
    - Stores execution history for each operation
         ↓
4c. Mutation Collection Stage:
    Project: collect_mutations()
    - Uses internal mutation suite handler (CosmicRaySuite)
    - Calls suite.get_mutants() to count mutants
    - CosmicRaySuite runs: cosmic-ray init, cr-xml (via subprocess)
    - Calls suite.get_survival_rate() for total MSR
    - CosmicRaySuite runs: cosmic-ray exec, cr-rate (via subprocess)
    - Updates ProjectModel.mutants_number and msr
    - For each test:
      * collect_mutations_for_test(): runs mutations with test alone
      * collect_mutations_without_test(): runs mutations without test
    - Updates TestModel.msr_alone and msr_without
    - Calculated properties auto-computed (impact, overlap, uniqueness, redundancy)
    - Stores execution history for each operation
         ↓
5. Database: All data persisted in work_dir/yagua.db
         ↓
6. CLI: Displays pipeline completion status
```

### Status and Report Flow

```
1. User: yagua status my_work_dir
         ↓
2. CLI: CLIManager.status()
   - Opens project via read_dir()
   - Calls ProjectManager.get_pipeline_status()
   - Displays: tests collected, coverage collected, mutations collected
```

## Architectural Patterns

### 1. Separation of Concerns
- **CLI**: User interface and command routing
- **ProjectManager**: Business logic with pipeline validation
- **Project**: Database access layer
- **TestSuites**: Test framework abstraction (subprocess-based)
- **MutationSuites**: Mutation framework abstraction (subprocess-based)
- **Models**: Data structure and persistence

### 2. Layered Architecture
- **Presentation Layer**: CLI commands
- **Business Logic Layer**: ProjectManager (pipeline validation, state tracking)
- **Data Access Layer**: Project (database operations)
- **Framework Adapters**: TestSuiteABC/MutationSuiteABC implementations
- **Data Layer**: Peewee ORM models

### 3. Dependency Injection
- Project manages internal suite handlers
- Suite handlers abstracted behind interfaces (TestSuiteABC, MutationSuiteABC)
- Subprocess-based execution for better isolation

### 4. Abstract Factory
- TestSuiteABC and MutationSuiteABC define interfaces
- Concrete implementations (PytestSuite, CosmicRaySuite) provide framework-specific logic
- Easy to add new frameworks without changing Project

### 5. Single Responsibility
- Each class has one clear purpose
- CLI handles user interaction and routing
- ProjectManager handles pipeline workflows
- Project handles database operations
- Suites handle framework-specific execution via subprocess
- Models handle data structure

### 6. Context Manager
- Project implements `__enter__` and `__exit__`
- Ensures database connections are properly closed
- Provides clean resource management

### 7. Session-Based Pipeline
- State tracking for resumability
- Each stage can be resumed independently
- Force re-execution via --rerun flag

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
import subprocess

class UnittestSuite(TestSuiteABC):
    def __init__(self, work_path):
        self._work_path = pathlib.Path(work_path) / "yagua_unittest"
        self._work_path.mkdir(parents=True, exist_ok=True)

    def _run(self, cmd, project_path):
        result = subprocess.run(
            cmd, cwd=project_path, capture_output=True, text=True
        )
        return (" ".join(cmd), result.returncode, result.stdout, result.stderr)

    def get_tests(self, project_path):
        # Implement unittest discovery via subprocess
        cmd = ["python", "-m", "unittest", "discover", "-v"]
        command, status, stdout, stderr = self._run(cmd, project_path)
        # Parse and return tests
        pass

    def get_coverage(self, project_path, project_name):
        # Implement unittest coverage via subprocess
        pass

    def get_coverage_for_tests(self, project_path, project_name, test_ids):
        # Implement coverage for specific tests
        pass
```

2. Export in `testsuites/__init__.py`:
```python
from .unittest_suite import UnittestSuite
__all__ = ["TestSuiteABC", "PytestSuite", "UnittestSuite"]
```

3. Use programmatically:
```python
from yagua.testsuites import UnittestSuite

proj = Project(work_dir)
proj._test_suite = UnittestSuite(proj.work_path)
proj.collect_tests()
```

### Adding New Mutation Frameworks

1. Create new class in `mutationsuites/`:
```python
from .abc import MutationSuiteABC
import subprocess

class MutmutSuite(MutationSuiteABC):
    def __init__(self, work_path, mutation_timeout=50.0):
        self._work_path = pathlib.Path(work_path) / "yagua_mutmut"
        self._work_path.mkdir(parents=True, exist_ok=True)
        self._mutation_timeout = float(mutation_timeout)

    def _run(self, cmd, project_path):
        # Implement subprocess execution
        pass

    def get_mutants(self, project_path, project_name, force):
        # Run mutmut via subprocess to count mutants
        pass

    def get_survival_rate(self, project_path, project_name, force):
        # Run full mutation testing
        pass

    def get_survival_rate_for_tests(self, project_path, project_name, test_ids, force):
        # Run mutations for specific tests
        pass
```

2. Export and configure in project

### Adding New CLI Commands

Add method to CLIManager:
```python
def my_command(
    self,
    work_dir: str = _make_work_dir_argument(),
) -> None:
    """Command description for help."""
    pm = read_dir(work_dir)
    # Implementation using ProjectManager
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
