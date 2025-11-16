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

    # Collect coverage for individual test
    test_id = "test_file.py::test_example"
    test_cov = proj.collect_coverage_for_test(suite, test_id)
    print(f"Test coverage: {test_cov:.2f}%")

    # Access project info via properties
    print(f"Project: {proj.name}")
    print(f"Path: {proj.path}")
    print(f"Description: {proj.description}")
    print(f"Coverage: {proj.coverage}")
```

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