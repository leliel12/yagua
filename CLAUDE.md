# CLAUDE.md

## Important Rules

**NEVER perform `git push` without explicit permission from the user.**

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

- **One Cache File Per Project**: Each SQLite file contains one project
- **Dynamic Model Binding**: Models bound to database at runtime in `Project.__init__()`
- **CLI Auto-Registration**: Methods in `CLIManager` auto-register as commands

## Commands

```bash
yagua create-project /path/to/project my_cache.db --name "Project" --work-path /path/to/work
yagua collect-tests project.db
yagua collect-coverage project.db
yagua list-tests project.db --long
yagua info project.db
```

## Code Style

- pep-8
- Code formater: 'black -l 79'
- Max 79 columns per line.
- NumPy-style docstrings (NO Examples section)
- Module organization: docstring → imports → constants → private helpers → classes → public functions
