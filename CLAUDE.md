# CLAUDE.md

## Important Rules

**NEVER perform `git push` or `git commit` without explicit permission from the user.**

## Project Overview

**yagua**: Python package for collecting and managing test/mutation information from pytest-based projects.

```
yagua/
├── __init__.py
├── models.py           # Peewee ORM models
├── project.py          # Project class - database management
├── cli.py              # Typer CLI commands
├── testsuites/         # Test suite handlers (TestSuiteABC, PytestSuite)
└── mutationsuites/     # Mutation suite handlers (MutationSuiteABC, CosmicRaySuite)
```

## Key Patterns

- **One Work Directory Per Project**: Each work directory contains yagua.db with one project
- **Dynamic Model Binding**: Models bound to database at runtime in `Project.__init__()`
- **CLI Auto-Registration**: Methods in `CLIManager` auto-register as commands

## Commands

```bash
yagua create-project /path/to/project my_work_dir --name "Project"
yagua collect-tests my_work_dir
yagua collect-coverage my_work_dir
yagua collect-mutations my_work_dir
yagua list-tests my_work_dir --long
yagua info my_work_dir
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
