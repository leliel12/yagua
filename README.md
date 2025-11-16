<div align="center">

<img src="https://github.com/leliel12/yagua/raw/master/res/logo.png" alt="Yagua Logo" width="300"/>

# Yagua

**A tool for collecting and managing test information from pytest-based projects**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## Table of Contents

- [About](#about)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [CLI](#cli)
  - [Programmatic API](#programmatic-api)
- [Coverage Metrics](#coverage-metrics)
  - [Basic Coverage Metrics](#basic-coverage-metrics)
  - [Calculated Coverage Metrics](#calculated-coverage-metrics)
  - [Example Usage](#example-usage)
  - [CLI Display](#cli-display)
  - [Use Cases](#use-cases)
- [Development](#development)
- [Documentation](#documentation)
- [License](#license)

---

## 📖 About

Yagua is a Python package that helps you collect, store, and manage test information from pytest-based projects using a SQLite database.

## ✨ Features

- **Test Discovery**: Collect test information from pytest-based projects
- **SQLite Storage**: Store test metadata in SQLite database (one cache file per project)
- **Coverage Tracking**: Track both project-level and per-test coverage information
- **Flexible API**: Both CLI and programmatic Python API
- **History Tracking**: Keep execution history for all operations
- **Force Recollection**: Option to force recollection of tests and coverage data

---

## 📦 Installation

```bash
# Install in development mode
pip install -e .

# Install with development dependencies (pytest, tox, mutmut, cosmic-ray)
pip install -e ".[dev]"
```

---

## 🚀 Quick Start

```bash
# Create a new project cache
yagua create-project /path/to/project

# Collect tests from the project
yagua collect-tests project.sqlite

# Show project information
yagua info project.sqlite

# List all tests
yagua list-tests project.sqlite

# Collect coverage information
yagua collect-coverage project.sqlite
```

---

## 💻 Usage

### 🖥️ CLI

```bash
# Show help
yagua --help

# Create a new project cache
yagua create-project /path/to/project
yagua create-project /path/to/project my_cache.sqlite --name "My Project" --description "Project description"

# Collect tests from a project
yagua collect-tests project.sqlite
yagua collect-tests project.sqlite --force  # Force recollection

# Show project information
yagua info project.sqlite

# List tests for a project
yagua list-tests project.sqlite
yagua list-tests project.sqlite --long  # Show all columns including IDs and timestamps

# Collect coverage information (project + per-test coverage)
yagua collect-coverage project.sqlite
yagua collect-coverage project.sqlite --force  # Force recalculation
```

### 🐍 Programmatic API

```python
from yagua import Project, PytestSuite

# Create a new project with metadata
proj = Project.from_project_info(
    name="my_project",
    path="/path/to/project",
    description="My awesome project",
    db_path="qa.sqlite"
)

# Open existing cache and use as context manager
with Project(db_path="qa.sqlite") as proj:
    # Collect and save tests from pytest suite
    suite = PytestSuite()
    saved, updated = proj.collect_tests(suite)
    print(f"Collected {saved + updated} tests")

    # Get all tests as DataFrame
    tests_df = proj.get_tests_dataframe()
    print(tests_df)

    # Count tests
    count = proj.count_tests()
    print(f"Total tests: {count}")

    # Collect coverage for all tests
    cov = proj.collect_coverage(suite)
    print(f"Coverage: {cov:.2f}%")

    # Collect coverage for individual test (alone)
    test_id = "test_file.py::test_example"
    test_cov_alone = proj.collect_coverage_for_test(suite, test_id)
    print(f"Test coverage alone: {test_cov_alone:.2f}%")

    # Collect coverage without individual test
    test_cov_without = proj.collect_coverage_without_test(suite, test_id)
    print(f"Coverage without test: {test_cov_without:.2f}%")

    # Access project info via properties
    print(f"Project: {proj.name}")
    print(f"Path: {proj.path}")
    print(f"Description: {proj.description}")
    print(f"Coverage: {proj.coverage}")
```

---

## 📊 Coverage Metrics

Yagua provides advanced coverage metrics to help you understand test quality, redundancy, and unique contributions. These metrics are automatically calculated when you run `collect-coverage`.

### Basic Coverage Metrics

- **Coverage Alone** (`coverage_alone`): Coverage percentage when running only this test in isolation
- **Coverage Without** (`coverage_without`): Coverage percentage when running all tests except this one

### Calculated Coverage Metrics

Yagua automatically calculates four additional metrics to help analyze test effectiveness:

#### 1. Coverage Impact

**Formula**: `coverage_impact = total_coverage - coverage_without`

**Meaning**: The unique coverage contribution of this test. This represents how much coverage would be lost if you removed this test from your suite.

**Interpretation**:
- **High Impact** (close to `coverage_alone`): Test contributes unique coverage, not well covered by other tests
- **Low Impact** (close to 0): Test coverage is mostly redundant, well covered by other tests
- **Negative Impact**: Should never occur with proper test suite

#### 2. Coverage Overlap

**Formula**: `coverage_overlap = total_coverage - coverage_alone`

**Meaning**: The amount of coverage that this test shares with other tests. This represents the portion of total coverage that is NOT unique to this test.

**Interpretation**:
- **High Overlap**: This test covers code that is already well covered by other tests
- **Low Overlap**: This test covers code that few other tests exercise

#### 3. Coverage Uniqueness

**Formula**: `coverage_uniqueness = (coverage_impact / coverage_alone) × 100`

**Meaning**: Percentage of this test's coverage that is unique (not covered by other tests).

**Interpretation**:
- **100%**: All coverage from this test is unique - removing it would significantly reduce total coverage
- **50%**: Half of this test's coverage is unique, half is redundant
- **0%**: None of this test's coverage is unique - completely redundant test

#### 4. Coverage Redundancy

**Formula**: `coverage_redundancy = ((coverage_alone - coverage_impact) / coverage_alone) × 100`

**Meaning**: Percentage of this test's coverage that is redundant (already covered by other tests).

**Interpretation**:
- **0%**: Test is completely unique - no redundant coverage
- **50%**: Half of this test's coverage is redundant
- **100%**: Test is completely redundant - all coverage duplicated by other tests

### Example Usage

```python
from yagua import Project, PytestSuite

with Project(db_path="qa.sqlite") as proj:
    suite = PytestSuite()

    # Collect all coverage metrics
    proj.collect_coverage(suite)

    # Get a specific test to access calculated properties
    test = proj.get_test("test_file.py::TestClass::test_example")

    # Access calculated metrics (auto-computed from coverage_alone and coverage_without)
    print(f"Coverage Impact: {test.coverage_impact:.2f}%")
    print(f"Coverage Overlap: {test.coverage_overlap:.2f}%")
    print(f"Coverage Uniqueness: {test.coverage_uniqueness:.2f}%")
    print(f"Coverage Redundancy: {test.coverage_redundancy:.2f}%")

    # High uniqueness = valuable test
    if test.coverage_uniqueness > 80:
        print("This test provides unique coverage - keep it!")

    # High redundancy = candidate for removal
    if test.coverage_redundancy > 90:
        print("This test is highly redundant - consider removing it")
```

### CLI Display

When you run `yagua collect-coverage project.sqlite`, all metrics are displayed in a comprehensive table:

```
🧪 Per-test coverage analysis:

┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ #  ┃ Test ID                 ┃ Alone   ┃ Without  ┃ Impact  ┃ Overlap  ┃ Uniqueness  ┃ Redundancy  ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ 1  │ test_foo.py::test_bar   │ 45.32%  │ 78.91%   │ +5.43%  │ 39.02%   │ 11.98%      │ 88.02%      │
│ 2  │ test_baz.py::test_qux   │ 67.89%  │ 71.23%   │ +13.11% │ 16.45%   │ 19.31%      │ 80.69%      │
└────┴─────────────────────────┴─────────┴──────────┴─────────┴──────────┴─────────────┴─────────────┘

Legend:
  • Alone = coverage running only this test
  • Without = coverage without this test
  • Impact = unique coverage contribution (total - without)
  • Overlap = coverage shared with other tests (total - alone)
  • Uniqueness = % of test's coverage that is unique (impact/alone × 100)
  • Redundancy = % of test's coverage that is redundant ((alone-impact)/alone × 100)
```

### Use Cases

**Identify Critical Tests**: Look for tests with high uniqueness (>80%) - these are critical for your coverage

**Find Redundant Tests**: Look for tests with high redundancy (>90%) - these are candidates for removal or refactoring

**Test Suite Optimization**: Balance coverage with test count by removing highly redundant tests

**Code Review**: Use impact metrics to justify new tests - high impact tests are valuable additions

---

## 🔧 Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=yagua --cov-report=term-missing

# Run mutation testing
mutmut run

# Run tox
tox
```

---

## 📚 Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Comprehensive architecture documentation explaining the global design, components, data flow, and architectural patterns
- [CLAUDE.md](CLAUDE.md) - Development guide with usage examples, API reference, and coding conventions

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

<div align="center">
<sub>Logo created with ChatGPT</sub>
</div>