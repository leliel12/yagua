# CLAUDE.md

## Important Rules

**NEVER perform `git push` or `git commit` without explicit permission from the user.**

## Project Overview

**yagua**: Python package for collecting and managing test/mutation information from pytest-based projects.

```
yagua/
├── __init__.py
├── models.py           # Peewee ORM models (ProjectModel, TestModel, HistoryModel)
├── project_store.py    # ProjectStore class - database access layer (DAL)
├── project.py          # Project class - business logic layer
├── cli.py              # Typer CLI commands (session-based pipeline pattern)
├── io.py               # Import/export operations (read_dir/read_archive return Project)
├── testsuites/         # Test suite handlers (TestSuiteABC, PytestSuite)
├── mutationsuites/     # Mutation suite handlers (MutationSuiteABC, CosmicRaySuite)
└── utils/              # Utility functions (df2rt for Rich table formatting)
```

## Key Patterns

- **One Work Directory Per Project**: Each work directory contains yagua.db with one project
- **Dynamic Model Binding**: Models bound to database at runtime in `ProjectStore.__init__()`
- **Layered Architecture**: `ProjectStore` (DAL) handles database operations, `Project` (business logic) handles pipeline validation and workflows
- **Session-Based Pipeline**: CLI implements resumable pipeline pattern with state tracking

## Commands

```bash
# Initialize a new project
yagua init /path/to/project my_work_dir --name "Project" --mutation-timeout 50.0

# Run the complete pipeline (tests, coverage, mutations)
yagua run my_work_dir

# Check pipeline status
yagua status my_work_dir

# View results report
yagua report my_work_dir

# Export project data
yagua export my_work_dir output.tar.gz
```

## Code Style

- pep-8
- Code formater: 'black -l 79'
- Max 79 columns per line.
- NumPy-style docstrings (NO Examples section)
- Module organization: docstring → imports → constants → private helpers → classes → public functions
- Import order (PEP 8):
  1. Standard library imports (alphabetically)
  2. Third-party library imports (alphabetically)
  3. Local/application imports (alphabetically)
  4. Each group separated by a blank line


## TODO

Cuando use claude, recordame que revise estos pendientes

> No hay pendientes