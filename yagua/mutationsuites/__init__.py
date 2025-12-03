"""Yagua - Mutation Suites Module.

This module provides mutation suite handlers for different mutation testing
frameworks. Suite handlers are responsible for running mutation testing and
collecting mutation score information from test projects using
framework-specific tools.

Available Handlers
------------------
MutationSuiteABC : class
    Abstract base class defining the interface for mutation suite handlers.
    Extend this class to add support for new mutation testing frameworks.
CosmicRaySuite : class
    Concrete implementation for cosmic-ray-based projects.
    Uses cosmic-ray's CLI for mutation testing.

Design Pattern
--------------
The mutation suite handler pattern separates mutation framework-specific logic
from the core Project management. This allows yagua to support multiple
mutation testing frameworks while keeping the Project API consistent.

Each handler implements two core methods:
- get_mutants(): Initialize mutation session and count total mutants
- get_survival_rate(): Run mutation testing and calculate survival rate

Extending Support
-----------------
To add support for a new mutation testing framework (e.g., mutmut, pit):

1. Create a new class that inherits from MutationSuiteABC
2. Implement all abstract methods
3. Return data in the format specified by MutationSuiteABC
4. Export the new class from this module
"""

from .abc import MutationSuiteABC
from .cosmicray_suite import CosmicRaySuite

__all__ = ["MutationSuiteABC", "CosmicRaySuite"]
