"""Yagua - Collection Layer.

This package contains the suite execution layer for Yagua, which handles
running test frameworks (pytest) and mutation testing frameworks
(cosmic-ray) to collect data.

The collection layer is responsible for:
- Executing test discovery and collection
- Running coverage analysis
- Performing mutation testing
- Returning collected data (does NOT persist to database)

Modules
-------
collector : module
    Collector class that coordinates suite execution.
testsuites : module
    Test suite handlers (pytest, etc.).
mutationsuites : module
    Mutation suite handlers (cosmic-ray, etc.).

Classes
-------
Collector : class
    Suite execution coordinator that runs test and mutation suites.
TestSuiteABC : class
    Abstract base class for test suite handlers.
PytestSuite : class
    Pytest test suite handler implementation.
MutationSuiteABC : class
    Abstract base class for mutation suite handlers.
CosmicRaySuite : class
    Cosmic-ray mutation suite handler implementation.
"""

from .collector import Collector
from .mutationsuites import CosmicRaySuite, MutationSuiteABC
from .testsuites import PytestSuite, TestSuiteABC

__all__ = [
    # Collector
    "Collector",
    # Test suites
    "TestSuiteABC",
    "PytestSuite",
    # Mutation suites
    "MutationSuiteABC",
    "CosmicRaySuite",
]
