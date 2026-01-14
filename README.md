<div align="center">

<img src="https://github.com/leliel12/yagua/raw/master/res/logo.png" alt="Yagua Logo" width="300"/>


**Software entropy analysis through test and mutation testing metrics**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## Table of Contents

- [About](#about)
- [Theoretical Foundation](#theoretical-foundation)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [CLI Commands](#cli-commands)
  - [Programmatic API](#programmatic-api)
- [Advanced Metrics](#advanced-metrics)
  - [Coverage Metrics](#coverage-metrics)
  - [Mutation Testing Metrics](#mutation-testing-metrics)
  - [Interpreting Results](#interpreting-results)
  - [Use Cases](#use-cases)
- [Development](#development)
- [Documentation](#documentation)
- [License](#license)

---

## 📖 About

Yagua is a Python package for collecting, storing, and analyzing test information from pytest-based projects. It uses a dedicated work directory containing an SQLite database (yagua.db) to store test metadata and coverage metrics, enabling efficient analysis without repeated execution of expensive coverage measurements.

**What Makes Yagua Different**: Unlike ad-hoc test quality metrics, yagua is grounded in a rigorous theoretical framework from statistical mechanics. It approximates **software entropy** by exploring the **local neighborhood of the mutation graph**—the space of syntactic variants (mutants) around your implementation. This provides a principled, computationally tractable approach to quantifying test suite quality, without needing to enumerate all possible programs (which would be intractable).

**Key Design Principle**: Yagua operates on a **caching-first** model. Once data is collected (tests, coverage metrics, mutations), it is cached and never recalculated unless explicitly requested using flags like `--force` or `-f`. This ensures fast operations and prevents unnecessary re-execution of expensive analysis.

## 🔬 Theoretical Foundation

Yagua is grounded in a rigorous theoretical framework that defines **software entropy** using principles from statistical mechanics. This foundation provides both theoretical justification and practical metrics for assessing test suite quality.

### Software Entropy: A Formal Definition

The concept of software entropy has long been used informally to describe the tendency of software systems to become more disordered and harder to maintain as they evolve. Yagua implements a formal definition based on statistical mechanics:

- **Microstates** (𝑝 ∈ ℙ): Concrete implementations of source code that satisfy a given specification
- **Macrostates** (t₁, ..., tₘ): Sets of tests that define observable properties of the system
- **Entropy Formula**: `S = -log W`, where `W` is the number of valid programs that pass the test suite

This formula is analogous to **Boltzmann's entropy** in physics, where entropy measures the number of microstates compatible with macroscopic constraints (like temperature and pressure). In software, tests play the role of macroscopic constraints.

### How Tests Reduce Entropy

Each test constrains the space of possible implementations:

- **High Entropy**: Many different programs could pass the test suite → high uncertainty about correct behavior → higher probability of bugs
- **Low Entropy**: Few programs satisfy the tests → behavior is well-specified → lower probability of unexpected behavior

**Adding non-redundant tests reduces entropy**, making the specification more precise and reducing the space of potential bugs.

### Connection to Mutation Testing

While computing the global entropy `S = -log W` is computationally intractable (it would require enumerating all possible programs of length L_code), **mutation testing provides a practical local approximation** by exploring the **mutation graph**:

#### The Mutation Graph G = (V, E_M)

- **Nodes (V)**: Programs (your implementation p_impl + all its mutants)
- **Edges (E_M)**: Connections via mutation operations (one syntactic change)
- **Subgraph G[ℙ]**: Syntactic variants that pass the test suite

**Key Insight**: Instead of exploring the entire (intractable) program space, yagua explores only the **local neighborhood** around your implementation in this graph.

#### How Yagua Uses the Graph

- **Mutation Testing** generates syntactic variants (mutants) one step away from p_impl
- **Surviving mutants** represent nearby programs in the microstate space that still pass the tests
- **Killing mutants** (by adding tests) reduces the local entropy
- **Graph Structure** reveals fragility:
  - **Many connected components** → tests are restrictive (good)
  - **Large connected basin** → tests are permissive (problematic)

The **Software Entropy Density (SED)** metric quantifies this local reduction:

```
SEDₗₒc = (log |M₀| - log |Mₘ|) / Lcode
```

Where `M₀` is mutants without tests and `Mₘ` is mutants that survive the full test suite, normalized by code length.

**Why This Works**: The local neighborhood provides an upper-bound proxy for the global entropy. If many mutants survive locally, the global entropy is likely high; if few survive, entropy is constrained.

### Why This Matters

This theoretical framework explains why the metrics computed by yagua are meaningful:

1. **MSR Impact**: Measures how much each test reduces local entropy
2. **MSR Uniqueness**: Identifies tests that eliminate microstates (mutants) no other test eliminates
3. **MSR Redundancy**: Identifies tests that eliminate microstates already eliminated by other tests

By measuring these quantities, yagua provides a **principled, theory-grounded approach** to assessing test suite quality, moving beyond ad-hoc metrics to measurements with clear physical interpretation.

For the complete theoretical development, see: *Fotinós, J. & Cabral, J.B. "A Formal Definition of Software Entropy" (in preparation)*.

## ✨ Features

- **Test Discovery**: Automatic collection of test information from pytest projects
- **SQLite Storage**: Dedicated work directory with yagua.db containing all test metadata
- **Coverage Analysis**: Project-level and per-test coverage tracking with advanced metrics
- **Dual Interface**: Both CLI and programmatic Python API
- **Execution History**: Complete audit trail of all operations with command tracking
- **Error Handling**: Comprehensive error logging even for failed executions
- **Flexible Recollection**: Force recalculation of any cached data on demand

---

## 📦 Installation

```bash
# Install in development mode
pip install -e .

# Install with development dependencies (pytest, coverage, pytest-cov)
pip install -e ".[dev]"
```

After installation, the `yagua` command will be available globally.

---

## 🚀 Quick Start

```bash
# Initialize a new yagua project (creates work directory with yagua.db)
yagua init /path/to/project _yagua_work_ \
    --name "Project" \
    --description "Project description" \
    --mutation-timeout 50.0

# Run the complete pipeline (collects tests, coverage, and mutations)
yagua run _yagua_work_

# Check pipeline status
yagua status _yagua_work_

# View results report
yagua report _yagua_work_

# Export project data
yagua export _yagua_work_ backup.tar.gz
```

---

## 💻 Usage

### 🖥️ CLI Commands

#### Project Initialization

```bash
# Show all available commands
yagua --help

# Initialize a new project
yagua init /path/to/project my_work_dir \
  --name "My Project" \
  --description "Project description" \
  --mutation-timeout 50.0
```

#### Pipeline Execution

```bash
# Run the complete pipeline (tests, coverage, mutations)
yagua run my_work_dir

# Force re-run the entire pipeline (ignores cache)
yagua run my_work_dir --rerun
yagua run my_work_dir -r  # Short form
```

**Note**: The pipeline execution can be time-consuming for large test suites. For N tests, coverage collection runs approximately 2N+1 test executions (total coverage + each test alone + all tests without each one). Mutation testing can take significantly longer depending on the number of mutants.

#### Status and Reporting

```bash
# Check pipeline execution status
yagua status my_work_dir

# View comprehensive results report
yagua report my_work_dir
```

#### Export and Import

```bash
# Export work directory to archive file
yagua export my_work_dir
yagua export my_work_dir --output backup.tar.gz

# Supported formats: .zip, .tar, .tar.gz (.tgz), .tar.bz2 (.tbz2), .tar.xz (.txz)
```

**Note**: Exported archives can be shared, backed up, or opened using the `read_archive()` function in the Python API.

### 🐍 Programmatic API

Yagua provides a complete Python API for integration into scripts and tools:

```python
from yagua import Project, ProjectManager, read_dir, read_archive

# Create new project (creates work_dir with yagua.db inside)
proj = Project.from_project_info(
    name="my_project",
    path="/path/to/project",
    work_dir="my_work_dir",
    description="Optional description",
    mutation_timeout=50.0
)
# Wrap in ProjectManager for business logic operations
pm = ProjectManager(proj)

# Open existing project from work directory (returns ProjectManager)
pm = read_dir("my_work_dir")

# Open project from an archive file (returns ProjectManager)
pm = read_archive("my_project.zip")

# Run the complete pipeline with progress tracking
def progress(current, total, test_id):
    print(f"Processing {current}/{total}: {test_id}")

result = pm.run_pipeline(
    rerun=False,  # Set to True to force re-execution
    progress_callback=progress
)

# Check pipeline status
status = pm.get_pipeline_status()
print(f"Tests collected: {status['tests_collected']}")
print(f"Coverage collected: {status['coverage_collected']}")
print(f"Mutations collected: {status['mutations_collected']}")

# Get tests as DataFrame
info = pm.get_tests_info()
tests_df = info['tests_df']

# Access project properties
project_info = pm.get_project_info()
print(f"Name: {project_info['name']}")
print(f"Path: {project_info['path']}")
print(f"Work Dir: {project_info['work_dir']}")
print(f"Database: {project_info['db_path']}")
print(f"Coverage: {project_info['coverage']}")
print(f"Total MSR: {project_info['msr']}")

# Close when done
pm.project.close()
```

For architectural details and system design, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 📊 Advanced Metrics

Yagua provides comprehensive metrics for analyzing test quality, redundancy, and unique contributions. These metrics are available for both **code coverage** and **mutation testing**, enabling deep insights into test suite effectiveness.

**Note**: These metrics are grounded in the [theoretical framework](#theoretical-foundation) of software entropy, where each metric has a clear interpretation in terms of reducing uncertainty about program behavior.

### Coverage Metrics

Coverage metrics analyze how much of your codebase is exercised by tests. All metrics are automatically calculated when running `yagua collect-coverage`.

#### Basic Coverage Metrics

These are directly measured by running pytest with coverage:

| Metric | Description |
|--------|-------------|
| **Coverage Alone** | Coverage when running only this test in isolation |
| **Coverage Without** | Coverage when running all tests except this one |
| **Total Coverage** | Overall project coverage with all tests |

#### Calculated Coverage Metrics

Yagua automatically derives four additional metrics from the basic measurements:

#### 1. Coverage Impact

**Formula**: `total_coverage - coverage_without`

**Meaning**: The unique coverage contribution of this test. How much coverage would be lost if you removed this test.

**Interpretation**:
- **High Impact** (close to coverage_alone): Test provides unique coverage
- **Low Impact** (close to 0): Test coverage is mostly redundant
- **Negative Impact**: Should never occur with a proper test suite

#### 2. Coverage Overlap

**Formula**: `coverage_alone - coverage_impact`
(Alternative: `coverage_without + coverage_alone - total_coverage`)

**Meaning**: Amount of coverage this test shares with other tests. The portion of this test's coverage that is NOT unique to it.

**Interpretation**:
- **High Overlap**: Code tested is mostly already covered by other tests
- **Low Overlap**: Code tested is exercised almost uniquely by this test

#### 3. Coverage Uniqueness (%)

**Formula**: `(coverage_impact / coverage_alone) × 100`

**Meaning**: Percentage of this test's coverage that is unique.

**Interpretation**:
- **100%**: All coverage is unique - critical test
- **50%**: Half unique, half redundant
- **0%**: Completely redundant test

#### 4. Coverage Redundancy (%)

**Formula**: `((coverage_alone - coverage_impact) / coverage_alone) × 100`

**Meaning**: Percentage of this test's coverage that is redundant.

**Interpretation**:
- **0%**: No redundant coverage - completely unique
- **50%**: Half redundant
- **100%**: Completely redundant - all coverage duplicated elsewhere

### Mutation Testing Metrics

Mutation testing metrics measure how effectively tests detect bugs by analyzing their ability to kill mutants (intentional code modifications). All metrics are automatically calculated when running `yagua collect-mutations`.

#### Basic MSR Metrics

These are directly measured by running mutation testing:

| Metric | Description |
|--------|-------------|
| **MSR Alone** | Mutation Score Ratio when running only this test in isolation |
| **MSR Without** | Mutation Score Ratio when running all tests except this one |
| **Total MSR** | Overall project Mutation Score Ratio with all tests |

#### Calculated MSR Metrics

Yagua automatically derives four additional metrics from the basic measurements:

#### 1. MSR Impact

**Formula**: `total_msr - msr_without`

**Meaning**: The unique contribution of this test to mutation detection. How many additional mutants would survive if you removed this test.

**Interpretation**:
- **High Impact** (close to msr_alone): Test kills mutants uniquely
- **Low Impact** (close to 0): Mutant kills are mostly redundant
- **Negative Impact**: Should never occur with a proper test suite

#### 2. MSR Overlap

**Formula**: `msr_alone - msr_impact`
(Alternative: `msr_without + msr_alone - total_msr`)

**Meaning**: Number of mutants killed by this test that are also killed by other tests. The portion of this test's mutation detection that is NOT unique to it.

**Interpretation**:
- **High Overlap**: Mutants killed are mostly caught by other tests too
- **Low Overlap**: Mutants killed are almost exclusively caught by this test

#### 3. MSR Uniqueness (%)

**Formula**: `(msr_impact / msr_alone) × 100`

**Meaning**: Percentage of this test's killed mutants that are unique.

**Interpretation**:
- **100%**: All mutant kills are unique - critical test for bug detection
- **50%**: Half unique, half redundant
- **0%**: Completely redundant test (all mutants caught by others)

#### 4. MSR Redundancy (%)

**Formula**: `((msr_alone - msr_impact) / msr_alone) × 100`

**Meaning**: Percentage of this test's killed mutants that are redundant.

**Interpretation**:
- **0%**: No redundant mutant kills - completely unique
- **50%**: Half redundant
- **100%**: Completely redundant - all mutant kills duplicated elsewhere

### Interpreting Results

The calculated metrics are available via the Python API using `proj.get_test(test_id)` which returns a pandas Series with all metrics, or displayed in the CLI using `yagua list-tests my_work_dir`:

![Test listing with coverage metrics](res/list_tests.png)

### Use Cases

#### Coverage Analysis

**Identify Critical Tests**
Tests with high coverage uniqueness (>80%) are critical for maintaining coverage. Removing them would significantly reduce overall coverage.

**Find Redundant Tests**
Tests with high coverage redundancy (>90%) are candidates for removal or refactoring. They test code already covered by other tests.

**Optimize Test Suite**
Balance coverage with test count by removing highly redundant tests while preserving high-uniqueness tests.

**Refactoring Guidance**
Tests with high coverage overlap indicate areas where code is well-tested, making refactoring safer.

#### Mutation Testing Analysis

**Identify Bug-Detecting Tests**
Tests with high MSR uniqueness (>80%) are critical for catching bugs. They detect issues that no other test catches.

**Find Ineffective Tests**
Tests with high MSR redundancy (>90%) kill mutants already caught by other tests. Consider removing or improving them.

**Prioritize Test Execution**
Run high-impact mutation tests first in CI/CD. They provide the most unique bug detection per execution time.

**Test Suite Quality Assessment**
Combine coverage and MSR metrics to identify tests that are both comprehensive (high coverage) and effective (high MSR impact).

**Code Review for Bug Detection**
Use MSR impact metrics to justify new tests. Tests with high MSR impact demonstrate they catch bugs other tests miss.

---

## 🔧 Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=yagua --cov-report=term-missing

# Format code (PEP 8 style, max 79 columns)
black -l 79 .
```

---

## 📚 Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture, components, data flow, and design patterns
- **[CLAUDE.md](CLAUDE.md)** - Development guide with API reference and coding conventions

---

## 📄 License

MIT License - See [LICENSE](LICENSE) for details.

---

<div align="center">
<sub>Logo created with ChatGPT</sub>
</div>
