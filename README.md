<div align="center">

<img src="https://github.com/leliel12/qa_entropy/raw/master/res/logo.png" alt="Yagua Logo" width="300"/>

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

## About

Yagua is a Python package that helps you collect, store, and manage test information from pytest-based projects using a SQLite database. Part of the **qa_entropy** research workspace.

## Features

- Collect test information from pytest projects
- Store test metadata in SQLite database (one cache file per project)
- Track test coverage information
- CLI and programmatic API
- Automatic project creation and updates

---

## Installation

```bash
# Install in development mode
pip install -e .

# Install with development dependencies (pytest, tox, mutmut, cosmic-ray)
pip install -e ".[dev]"
```

---

## Quick Start

```bash
# Create a new project cache
yagua create-project /path/to/project

# Collect tests from the project
yagua collect project.sqlite

# Show project information
yagua info project.sqlite

# List all tests
yagua list-tests project.sqlite

# Collect coverage information
yagua coverage project.sqlite
```

---

## Usage

### CLI

```bash
# Show help
yagua --help

# Create a new project cache
yagua create-project /path/to/project
yagua create-project /path/to/project my_cache.sqlite --name "My Project" --description "Project description"

# Collect tests from a project
yagua collect project.sqlite

# Show project information
yagua info project.sqlite

# List tests for a project
yagua list-tests project.sqlite

# Collect coverage information
yagua coverage project.sqlite
yagua coverage project.sqlite --force  # Force recalculation
```

### Programmatic API

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

    # List all tests as DataFrame
    tests_df = proj.list_tests()
    print(tests_df)

    # Count tests
    count = proj.count_tests()
    print(f"Total tests: {count}")

    # Collect coverage
    cov = proj.collect_coverage(suite)
    print(f"Coverage: {cov:.2f}%")

    # Access project info via magic methods
    print(f"Project: {proj.name}")
    print(f"Path: {proj.path}")
    print(f"Description: {proj.description}")
```

---

## Development

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

## Documentation

See [CLAUDE.md](CLAUDE.md) for detailed architecture and development documentation.

## License

MIT License - See [LICENSE](LICENSE) for details.

---

<div align="center">
<sub>Logo created with ChatGPT</sub>
</div>