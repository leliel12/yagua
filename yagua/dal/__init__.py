"""Yagua - Data Access Layer (DAL).

This package contains the data access layer components for Yagua,
including ORM models and the ProjectStore class for database operations.

Modules
-------
models : module
    Peewee ORM models for project, test, and history data.
project_store : module
    ProjectStore class for database operations.

Classes
-------
BaseModel : class
    Base model class for all Peewee models.
ProjectModel : class
    Model for project metadata.
TestModel : class
    Model for test information and metrics.
HistoryModel : class
    Model for execution history tracking.
ProjectStore : class
    Data access layer for project database operations.

Constants
---------
MODELS_TO_CREATE : list
    Models that need to have tables created in the database.
ALL_MODELS : list
    All models that need to be bound to the database instance.
"""

from .models import BaseModel, HistoryModel, ProjectModel, TestModel
from .project_store import (
    ALL_MODELS,
    MODELS_TO_CREATE,
    ProjectStore,
)

__all__ = [
    # Models
    "BaseModel",
    "ProjectModel",
    "TestModel",
    "HistoryModel",
    # Store
    "ProjectStore",
    # Constants
    "MODELS_TO_CREATE",
    "ALL_MODELS",
]
