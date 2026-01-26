# Yagua Architecture

This document explains the architecture of Yagua, a tool for collecting and managing test and mutation information from pytest-based projects.

## Overview

Yagua uses a 3-layer architecture with subprocess-based framework adapters:

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
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Data Access Layer                             │
│  (project_store.py) - Database ops, suite orchestration          │
└────────┬──────────────────┬──────────────────┬──────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
   ┌──────────┐      ┌────────────┐     ┌─────────────┐
   │  Test    │      │ Mutation   │     │   Models    │
   │  Suites  │      │  Suites    │     │ (Peewee ORM)│
   │(subprocess)│     │(subprocess)│    └─────────────┘
   └──────────┘      └────────────┘
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

### 2. Business Logic (`project.py`)

**Project** wraps ProjectStore to provide:
- Pipeline validation and state tracking
- Stage execution with caching
- Progress callbacks
- Resumability (skip completed stages)

**Key Methods**:
- `run_pipeline(rerun=False)`: Execute complete workflow
- `get_pipeline_status()`: Check stage completion

### 3. Data Access Layer (`project_store.py`)

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
- Test collection: `collect_tests()`, `add_test()`
- Coverage: `collect_coverage()`, `collect_coverage_for_test()`, `collect_coverage_without_test()`
- Mutations: `collect_mutations()`, `collect_mutations_for_test()`, `collect_mutations_without_test()`
- Suite orchestration via TestSuiteABC/MutationSuiteABC

### 4. Framework Adapters (subprocess-based)

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

### 5. Data Models (`models.py`)

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
CLIManager.run()
  ↓
Project.run_pipeline()
  ↓
1. collect_tests() → PytestSuite (subprocess)
2. collect_coverage() → PytestSuite (subprocess, N tests = 2N+1 runs)
3. collect_mutations() → CosmicRaySuite (subprocess)
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

1. **Layered Architecture**: CLI → Project → ProjectStore → Suites
2. **Subprocess Isolation**: External commands for pytest/cosmic-ray
3. **Session-Based Pipeline**: Resumable, cached stages
4. **Hash-Based Files**: Deterministic temp file naming (MD5)
5. **Abstract Factory**: TestSuiteABC/MutationSuiteABC for extensibility
6. **Context Manager**: Project auto-closes database
7. **Dynamic Binding**: Models bound to database at runtime

## Database Architecture

- **One work_dir per project**: Each contains yagua.db with one ProjectModel (id=1)
- **Runtime binding**: Models dynamically bound to SqliteDatabase instance in ProjectStore
- **Transaction management**: All operations wrapped in transactions
- **Calculated properties**: Metrics auto-computed via hybrid properties

## Extending Yagua

### Add Test Framework

```python
from yagua.testsuites import TestSuiteABC
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
from yagua.mutationsuites import MutationSuiteABC

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
