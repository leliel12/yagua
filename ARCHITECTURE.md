# Yagua Architecture

This document explains the architecture of Yagua, a tool for collecting and managing test and mutation information from pytest-based projects.

## Overview

Yagua uses a 4-layer architecture with subprocess-based framework adapters:

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Layer                               │
│          (cli.py) - Command routing, user interface             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                         │
│     (project.py) - Pipeline validation, state tracking           │
└──────────────────┬────────────────────────────┬─────────────────┘
                   │                            │
                   ▼                            ▼
   ┌───────────────────────────┐    ┌──────────────────────────┐
   │  Suite Execution Layer    │    │   Data Access Layer      │
   │ (collector.py)            │    │ (project_store.py)       │
   │ - Orchestrates suites     │    │ - Database operations    │
   │ - Returns collected data  │    │ - Data persistence       │
   └────────┬──────────────────┘    └──────────┬───────────────┘
            │                                   │
            ▼                                   ▼
   ┌──────────────────┐                 ┌─────────────┐
   │  Framework Suites│                 │   Models    │
   │  - Test Suites   │                 │ (Peewee ORM)│
   │  - Mutation Suites│                └─────────────┘
   │  (subprocess)    │
   └──────────────────┘
```

## Layers

### 1. CLI Layer (`cli.py`)

**Commands**:
- `init`: Initialize project with yagua.db
- `run`: Execute pipeline (tests → coverage → mutations)
- `status`: Show pipeline execution status
- `report`: Display comprehensive results
- `export`: Archive project data

**Pattern**: Session-based pipeline with resumability

### 2. Business Logic Layer (`project.py`)

**Project** coordinates Collector and ProjectStore to provide:
- Pipeline validation and state tracking
- Stage execution with caching
- Progress callbacks
- Resumability (skip completed stages)
- Orchestration between suite execution (Collector) and data persistence (ProjectStore)

**Key Methods**:
- `run_pipeline(rerun=False)`: Execute complete workflow
- `get_pipeline_status()`: Check stage completion

### 3. Suite Execution Layer (`collector.py`)

**Collector** orchestrates test and mutation suite execution:

```python
# Create collector
collector = Collector(
    project_path="/path/to/project",
    work_path="/path/to/work_dir",
    mutation_timeout=50.0
)

# Collect tests
tests_data = collector.collect_tests()

# Collect coverage
coverage_data = collector.collect_coverage(test_ids, progress_callback)

# Collect mutations
mutations_data = collector.collect_mutations(test_ids, progress_callback)
```

**Responsibilities**:
- Execute test suites (pytest) via TestSuiteABC implementations
- Execute mutation suites (cosmic-ray) via MutationSuiteABC implementations
- Return collected data to caller (does NOT persist to database)
- Provide progress callbacks during long-running operations

**Key Methods**:
- `collect_tests()`: Discover tests in the project
- `collect_coverage(test_ids, callback)`: Measure coverage for tests
- `collect_mutations(test_ids, callback)`: Run mutation testing

### 4. Data Access Layer (`project_store.py`)

**ProjectStore** handles database operations:

```python
# Create new
store = ProjectStore.from_project_info(
    name="name", path="/project", work_dir="/work", mutation_timeout=50.0
)

# Open existing
store = ProjectStore(work_dir="/work")
```

**Responsibilities**:
- Database connection management and model binding
- CRUD operations for projects, tests, and history
- Transaction management for ACID compliance
- Data persistence for test metadata, coverage, and mutations

**Key Methods**:
- `add_test()`: Save test to database
- `update_coverage()`: Update coverage metrics for a test
- `update_mutations()`: Update mutation metrics for a test
- `get_tests()`: Query tests from database

### 5. Framework Adapters (subprocess-based)

**Test Suites** (`testsuites/`):
- `TestSuiteABC`: Abstract interface
- `PytestSuite`: Runs pytest via subprocess
  - `pytest --collect-only`: Test discovery
  - `pytest --cov`: Coverage measurement
  - Hash-based temp files (deterministic naming)

**Mutation Suites** (`mutationsuites/`):
- `MutationSuiteABC`: Abstract interface
- `CosmicRaySuite`: Runs cosmic-ray via subprocess
  - `cosmic-ray init`: Initialize session
  - `cosmic-ray exec`: Run mutations
  - `cr-xml`: Get mutant count
  - `cr-rate`: Calculate survival rate
  - Manual TOML config (better isolation)
  - Respects `mutation_timeout` parameter

### 6. Data Models (`dal/models.py`)

**ProjectModel** (singleton, id=1):
- Metadata: name, path, work_path, description
- Results: coverage, mutants_number, msr
- Suite names: test_suite_name, mutation_suite_name

**TestModel**:
- Base data: test_id, file, suite, test
- Coverage: coverage_alone, coverage_without
- Mutations: msr_alone, msr_without
- Calculated properties: impact, overlap, uniqueness, redundancy (auto-computed)

**HistoryModel**:
- Execution audit: tag, command, status_code, stdout, stderr, result

## Data Flow

### Pipeline Execution

```
yagua run work_dir
  ↓
CLI Layer: typer command
  ↓
Business Logic: Project.run_pipeline()
  ↓
  ├─> Suite Execution: Collector.collect_tests()
  │     ↓
  │   PytestSuite (subprocess) → returns test data
  │     ↓
  │   Data Access: ProjectStore.add_test() → persists to DB
  │
  ├─> Suite Execution: Collector.collect_coverage()
  │     ↓
  │   PytestSuite (subprocess, N tests = 2N+1 runs) → returns coverage data
  │     ↓
  │   Data Access: ProjectStore.update_coverage() → persists to DB
  │
  └─> Suite Execution: Collector.collect_mutations()
        ↓
      CosmicRaySuite (subprocess) → returns mutation data
        ↓
      Data Access: ProjectStore.update_mutations() → persists to DB
        ↓
Database: All data persisted to work_dir/yagua.db
```

**Coverage Collection** (per test):
- Total coverage: all tests together
- Coverage alone: single test in isolation
- Coverage without: all tests except one
- Calculated: impact, overlap, uniqueness, redundancy

**Mutation Collection** (per test):
- Total MSR: all tests together
- MSR alone: single test in isolation
- MSR without: all tests except one
- Calculated: impact, overlap, uniqueness, redundancy

## Key Design Patterns

1. **Layered Architecture**: CLI → Project → Collector + ProjectStore → Suites
2. **Separation of Concerns**: Collector (execution) vs ProjectStore (persistence)
3. **Subprocess Isolation**: External commands for pytest/cosmic-ray
4. **Session-Based Pipeline**: Resumable, cached stages
5. **Hash-Based Files**: Deterministic temp file naming (MD5)
6. **Abstract Factory**: TestSuiteABC/MutationSuiteABC for extensibility
7. **Context Manager**: Project auto-closes database
8. **Dynamic Binding**: Models bound to database at runtime

## Database Architecture

- **One work_dir per project**: Each contains yagua.db with one ProjectModel (id=1)
- **Runtime binding**: Models dynamically bound to SqliteDatabase instance in ProjectStore
- **Transaction management**: All operations wrapped in transactions
- **Calculated properties**: Metrics auto-computed via hybrid properties

## Extending Yagua

### Add Test Framework

```python
from yagua.collection.testsuites import TestSuiteABC
import pathlib
import subprocess

class UnittestSuite(TestSuiteABC):
    def __init__(self, work_path):
        self._work_path = pathlib.Path(work_path) / "yagua_unittest"
        self._work_path.mkdir(parents=True, exist_ok=True)

    def _run(self, cmd, project_path):
        result = subprocess.run(cmd, cwd=project_path, capture_output=True, text=True)
        return (" ".join(cmd), result.returncode, result.stdout, result.stderr)

    def get_tests(self, project_path):
        # Implement using subprocess
        pass
```

### Add Mutation Framework

```python
from yagua.collection.mutationsuites import MutationSuiteABC
import pathlib

class MutmutSuite(MutationSuiteABC):
    def __init__(self, work_path, mutation_timeout=50.0):
        self._work_path = pathlib.Path(work_path) / "yagua_mutmut"
        self._mutation_timeout = float(mutation_timeout)

    def get_mutants(self, project_path, project_name, force):
        # Run mutmut via subprocess
        pass
```

## Technology Stack

- **CLI**: Typer (type-safe command builder)
- **ORM**: Peewee (lightweight, simple)
- **Database**: SQLite (embedded, zero-config)
- **Data**: Pandas (DataFrames for analysis)
- **Execution**: subprocess (external tool isolation)
- **Language**: Python 3.10+ (modern type hints)
