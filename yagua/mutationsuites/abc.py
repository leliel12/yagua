"""Yagua - Mutation Suite Abstract Base Class.

This module defines the abstract interface that all mutation suite handlers
must implement to integrate with yagua's mutation testing and analysis system.

Classes
-------
SuiteRunResult : dataclass
    Structured result from a mutation suite execution containing the value,
    command, status code, stdout, stderr, and additional data.
SuiteRunResultError : Exception
    Exception raised when a suite run fails (non-zero exit status).
MutationSuiteABC : ABC
    Abstract base class defining the required interface for mutation suite
    handlers.

Interface Contract
------------------
All mutation suite handlers must implement two abstract methods that return
SuiteRunResult instances or compatible tuple structures:

1. get_mutants(project_path, project_name, force) -> SuiteRunResult
   - Runs mutation initialization to count mutants
   - Returns result with mutants_number as value

2. test_mutations(project_path, project_name, force) -> SuiteRunResult
   - Executes all mutations against all tests
   - Returns result with survival_rate as value

Return Value Format
-------------------
Methods can return either SuiteRunResult instances or 6-tuple structures:
- value: Primary result (mutants count or mutation score percentage)
- command: Command string that was executed
- status_code: Exit status (0 = success, non-zero = error)
- stdout: Standard output from command
- stderr: Standard error from command
- result: Additional framework-specific data

This format enables comprehensive audit logging through HistoryModel.

Notes
-----
The abstract methods use @abstractmethod decorator, ensuring that concrete
implementations must provide all required functionality. Attempting to
instantiate a subclass without implementing all abstract methods will raise
TypeError.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


# ============================================================================
# EXCEPTIONS
# ============================================================================


class SuiteRunResultError(Exception):
    """Exception raised when a mutation suite command fails.

    This exception is raised by SuiteRunResult.raise_if_error() when the
    suite execution returns a non-zero exit status code, indicating an
    error occurred during mutation testing.

    Parameters
    ----------
    result : _SuiteRunResult
        The complete SuiteRunResult object containing all execution
        information including command, status code, stdout, and stderr.

    Attributes
    ----------
    result : _SuiteRunResult
        The full result object that triggered the exception, providing
        access to all execution details for debugging.

    See Also
    --------
    _SuiteRunResult : The dataclass that raises this exception.
    """

    def __init__(self, result):
        """Initialize the exception with the complete result object.

        Parameters
        ----------
        result : _SuiteRunResult
            The SuiteRunResult instance containing command execution details.
        """
        self.result = result
        super().__init__(f"{result.command} - Exit Code {result.status_code}")


# ============================================================================
# MUTATION SUITE RESULT DATACLASS
# ============================================================================


@dataclass(frozen=True)
class _SuiteRunResult:
    """Structured result from a mutation suite execution.

    This dataclass provides a standardized format for capturing the complete
    outcome of running mutation suite commands (e.g., mutation score
    calculation). It encapsulates both the primary result value and all
    execution metadata necessary for debugging, logging, and audit trails.

    Attributes
    ----------
    value : object
        The primary result value from the operation. Type varies by operation:
        - For get_mutations(): float | None (mutation score percentage 0-100)
        - For get_mutations_for_tests(): float | None (mutation score)
    command : str
        The complete command string that was executed (e.g.,
        "cosmic-ray run config.toml").
        This enables reproducibility and audit logging.
    status_code : int
        The exit status code from the command execution. Zero indicates
        success; non-zero values indicate errors. Follows standard Unix
        convention.
    stdout : str
        Standard output captured from the command execution. Contains the
        normal output text produced by the mutation suite runner.
    stderr : str
        Standard error captured from the command execution. Contains error
        messages, warnings, and diagnostic information.
    result : object
        Additional framework-specific data or metadata. Can contain:
        - Raw mutation testing output
        - Parsed mutation results
        - Framework-specific objects
        - Any supplementary information not captured in other fields

    Notes
    -----
    This class replaces the older tuple-based return format with a more
    explicit and self-documenting structure. It provides better type hints
    and makes code more maintainable by using named fields instead of
    positional tuple elements.

    The dataclass decorator automatically generates __init__, __repr__,
    __eq__, and other useful methods.

    See Also
    --------
    MutationSuiteABC : Abstract base class that uses this dataclass.
    CosmicRaySuite : Concrete implementation that returns SuiteRunResult
        instances.

    """

    value: object
    command: str
    status_code: int
    stdout: str
    stderr: str
    result: object

    @property
    def error(self):
        """Check if the command execution resulted in an error.

        Returns
        -------
        bool
            True if the status_code is non-zero (indicating an error),
            False if the status_code is zero (indicating success).

        """
        return self.status_code > 0

    def raise_if_error(self):
        """Raise an exception if the command execution failed.

        This method checks the error property and raises a
        SuiteRunResultError if the command returned a non-zero exit
        status. This is useful for enforcing error handling in
        mutation suite operations.

        Raises
        ------
        SuiteRunResultError
            If status_code is non-zero, raises an exception containing
            the status code and stderr output.

        See Also
        --------
        error : Property that checks for error status.
        SuiteRunResultError : The exception raised by this method.
        """
        if self.error:
            raise SuiteRunResultError(self)


class MutationSuiteABC(ABC):
    """Abstract base class for mutation suite handlers.

    This class defines the interface that all mutation suite implementations
    must follow. Subclasses should implement methods for running mutation
    testing from different mutation testing frameworks.

    All concrete implementations must provide two methods:
    - get_mutants(): For counting total mutants generated
    - test_mutations(): For executing mutations and calculating survival rate

    The consistent return format across all methods enables yagua to
    store comprehensive audit logs of all operations in HistoryModel.

    See Also
    --------
    CosmicRaySuite : Concrete implementation for cosmic-ray mutation testing.
    """

    def __init__(self, work_path):
        """Initialize mutation suite handler with working directory.

        Parameters
        ----------
        work_path : str or Path
            Path to working directory for storing intermediate files
            (e.g., mutation databases, configuration files).
        """
        pass

    def pkg_result(
        self, *, value, command, status_code, stdout, stderr, result
    ):
        """Package mutation suite execution results into a SuiteRunResult.

        This helper method creates a standardized SuiteRunResult dataclass
        instance from mutation suite execution data. It ensures consistent
        return format across all mutation suite handler methods.

        Parameters
        ----------
        value : object
            The primary result value (mutation score percentage).
        command : str
            The command string that was executed.
        status_code : int
            Exit status code (0 = success, non-zero = error).
        stdout : str
            Standard output captured from command execution.
        stderr : str
            Standard error captured from command execution.
        result : object
            Additional framework-specific data or metadata.

        Returns
        -------
        _SuiteRunResult
            Immutable dataclass containing all execution results and metadata.

        Notes
        -----
        This method should be used by all abstract method implementations
        (get_mutations, get_mutations_for_tests) to ensure consistent return
        format for audit logging and result processing.

        See Also
        --------
        _SuiteRunResult : The dataclass returned by this method.
        """
        return _SuiteRunResult(
            value=value,
            command=command,
            status_code=status_code,
            stdout=stdout,
            stderr=stderr,
            result=result,
        )

    # ========================================================================
    # Abstract Methods
    # ========================================================================

    @abstractmethod
    def get_mutants(self, project_path, project_name) -> _SuiteRunResult:
        """Run mutation analysis and return the number of mutants.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run mutation testing on.
        project_name : str
            Name of the project/package to mutate.

        Returns
        -------
        mutants_number : int | None
            Number of mutants generated or None if count could not
            be determined.
        command : str
            The command that was executed to initialize mutations.
        stdout : str
            Standard output from the command execution.
        stderr : str
            Standard error output from the command execution.
        data : object
            Additional mutation data (e.g., detailed mutation results).

        Notes
        -----
        The return tuple provides complete information about the mutation
        initialization process, allowing the caller to log the command executed
        and store execution details (stdout, stderr, and additional data)
        for audit purposes.
        """
        pass

    @abstractmethod
    def test_mutations(
        self, project_path, project_name, force
    ) -> _SuiteRunResult:
        """Execute mutation testing and return the survival rate.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run mutation testing on.
        project_name : str
            Name of the project/package to mutate.
        force : bool
            Force re-execution of mutations even if already run.

        Returns
        -------
        survival_rate : float | None
            Mutation survival rate percentage (0-100) or None if score
            could not be determined.
        command : str
            The command that was executed to run mutations.
        stdout : str
            Standard output from the command execution.
        stderr : str
            Standard error output from the command execution.
        data : object
            Additional mutation data (e.g., detailed mutation results).

        Notes
        -----
        This method executes all mutations against all tests and calculates
        the survival rate (percentage of mutants that survived). The
        mutation score can be calculated as (1 - survival_rate/100).
        """
        pass
