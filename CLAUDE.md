# CLAUDE.md

## Important Rules

**NEVER perform `git push` or `git commit` without explicit permission from the user.**

## Project Overview

**yagua**: Python package for collecting and managing test/mutation information from pytest-based projects.

```
yagua/
├── __init__.py
├── project.py          # Project class - business logic layer
├── cli.py              # Typer CLI commands (session-based pipeline pattern)
├── io.py               # Import/export operations (read_dir/read_archive return Project)
├── dal/                # Data Access Layer package
│   ├── __init__.py
│   ├── models.py       # Peewee ORM models (ProjectModel, TestModel, HistoryModel)
│   └── project_store.py # ProjectStore class - database operations
├── collection/         # Suite Execution Layer package
│   ├── __init__.py
│   ├── collector.py    # Collector class - orchestrates suite execution
│   ├── testsuites/     # Test suite handlers (TestSuiteABC, PytestSuite)
│   │   ├── __init__.py
│   │   ├── abc.py
│   │   └── pytest_suite.py
│   └── mutationsuites/ # Mutation suite handlers (MutationSuiteABC, CosmicRaySuite)
│       ├── __init__.py
│       ├── abc.py
│       └── cosmicray_suite.py
└── utils/              # Utility functions (df2rt for Rich table formatting)
    ├── __init__.py
    └── df2rt.py
```

## Key Patterns

- **One Work Directory Per Project**: Each work directory contains yagua.db with one project
- **Dynamic Model Binding**: Models bound to database at runtime in `ProjectStore.__init__()`
- **Layered Architecture**:
  - `ProjectStore` (DAL) handles database operations
  - `Collector` (Suite Execution Layer) orchestrates test/mutation suite execution
  - `Project` (Business Logic) handles pipeline validation and workflows
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

### Problemas Identificados

1. ✅ **CORREGIDO - BUG en project.py línea 457**:
   - Cambiado el ordenamiento de tests para usar `coverage_alone` en lugar de `coverage_uniqueness`
   - Los tests ahora se priorizan por su cobertura individual durante la recolección de mutaciones
   - Actualizado también el comentario en cli.py para reflejar el cambio

2. ✅ **CORREGIDO - Inconsistencia terminológica MSR**:
   - Actualizada la documentación en models.py para aclarar que MSR = "Mutation Survival Ratio"
   - MSR representa el % de mutantes que SOBREVIVIERON (no fueron matados)
   - Valores más bajos indican test suites más efectivos
   - Agregada nota: mutation_score = 100 - msr