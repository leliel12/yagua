"""Yagua - Cosmic Ray Suite Handler.

This module provides a mutation suite handler for cosmic-ray-based projects,
implementing the MutationSuiteABC interface using cosmic-ray's CLI.

Classes
-------
CosmicRaySuite : class
    Main mutation suite handler for cosmic-ray-based mutation testing.

Implementation Details
----------------------
This implementation uses:
- cosmic-ray CLI for running mutation testing
- SQLite database for mutation results storage
- Temporary files for mutation configuration and results

Key Features
------------
- Configurable mutation operators
- Per-test mutation score calculation
- Complete audit trail (captures command, stdout, stderr, and results)

Dependencies
------------
- cosmic-ray: Mutation testing framework for Python
"""

import io
import contextlib
import os
import pathlib
import tempfile
import xml.etree.ElementTree as ET

from cosmic_ray import config as cray_config
from cosmic_ray import cli as cray_cli
from cosmic_ray.tools import xml as cr_xml

from .abc import MutationSuiteABC


# ============================================================================
# COSMIC RAY SUITE
# ============================================================================


class BytesAndStringIO(io.StringIO):
    """StringIO that accepts both bytes and strings for writing.

    This class extends io.StringIO to handle both bytes and string inputs,
    automatically decoding bytes to UTF-8 strings. It also provides a
    buffer property that returns self, making it compatible with APIs
    that expect a file-like object with a buffer attribute.

    Notes
    -----
    This is useful for redirecting stdout/stderr when working with
    libraries that may write either bytes or strings to output streams.
    """

    @property
    def buffer(self):
        """Return self as the buffer.

        Returns
        -------
        BytesAndStringIO
            Returns the instance itself to satisfy buffer attribute access.
        """
        return self

    def write(self, s, /):
        """Write string or bytes to the stream.

        Parameters
        ----------
        s : str or bytes
            String or bytes to write. Bytes are automatically decoded
            to UTF-8 before writing.

        Returns
        -------
        int
            Number of bytes written (before decoding if bytes input).
        """
        rv = len(s)
        if isinstance(s, bytes):
            s = s.decode("utf-8")
        super().write(s)
        return rv


class ExitCalled(Exception):
    """Exception raised when SystemExit is caught during command execution.

    This exception is used internally to handle cases where cosmic-ray
    commands call sys.exit(), converting them into catchable exceptions
    that can be processed for exit code extraction.
    """

    pass


class CosmicRaySuite(MutationSuiteABC):
    """Mutation suite handler for cosmic-ray-based projects.

    This class implements the MutationSuiteABC interface for projects using
    cosmic-ray for mutation testing, providing methods to run mutations and
    calculate mutation scores.

    The class uses subprocess calls to cosmic-ray CLI commands and returns
    structured data including the executed command, output, and additional
    metadata for audit logging purposes.

    Attributes
    ----------
    _temp_dir : tempfile.TemporaryDirectory
        Temporary directory for storing mutation databases and config files.

    Notes
    -----
    This implementation requires cosmic-ray to be installed in the
    environment where the project mutations are being tested.
    """

    # ========================================================================
    # Constructor
    # ========================================================================

    def __init__(self, work_path):
        """Initialize CosmicRaySuite with working directory.

        Parameters
        ----------
        work_path : str or Path
            Path to the working directory where intermediate files
            (e.g., mutation databases, configuration files) will be stored.
        """
        self._verbose = False
        self._work_path = pathlib.Path(work_path) / "yagua_cray"
        self._work_path.mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _render_full_cmd(self, func, args, kwargs):
        """Render a function call as a string for logging.

        Parameters
        ----------
        func : callable
            Function whose call will be rendered.
        args : tuple
            Positional arguments to the function.
        kwargs : dict
            Keyword arguments to the function.

        Returns
        -------
        str
            String representation of the function call
            (e.g., "func_name(arg1, arg2, key=value)").
        """
        func = func.__name__
        args = ", ".join(map(repr, args))
        kwargs = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        kwargs = f", {kwargs}" if kwargs else ""
        return f"{func}({args}, {kwargs})"

    def _run(self, project_path, func, args=None, kwargs=None):
        """Run a cosmic-ray function with captured output.

        This internal method executes cosmic-ray functions programmatically,
        redirecting output to string buffers and changing to the project
        directory.

        Parameters
        ----------
        project_path : str or Path
            Working directory for cosmic-ray execution.
        func : callable
            Cosmic-ray function to execute (e.g., cray_cli.init.callback).
        args : tuple, optional
            Positional arguments to pass to func. Default is None (empty
            tuple).
        kwargs : dict, optional
            Keyword arguments to pass to func. Default is None (empty dict).

        Returns
        -------
        command : str
            String representation of the function call for audit logging.
        status : int
            Exit status code (0 = success, non-zero from SystemExit).
        stdout : str
            Captured standard output from function execution.
        stderr : str
            Captured standard error from function execution.

        Notes
        -----
        This method uses context managers to:
        1. Change to the project directory (contextlib.chdir)
        2. Redirect stdout to a BytesAndStringIO buffer
        3. Redirect stderr to a BytesAndStringIO buffer
        4. Catch SystemExit and extract the exit code

        All context changes are automatically reverted when the method
        returns.
        """
        args = args or ()
        kwargs = kwargs or {}
        stdout, stderr = BytesAndStringIO(), BytesAndStringIO()
        full_cmd = self._render_full_cmd(func, args, kwargs)

        status = 0

        if self._verbose:
            print(f"[RUN] {project_path} >> {full_cmd!r}")

        try:
            with (
                contextlib.chdir(project_path),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                func(*args, **kwargs)
        except SystemExit as exit:
            status = exit.code

        stdout.flush()
        stderr.flush()

        return (full_cmd, status, stdout.getvalue(), stderr.getvalue())

    def _resolve_module_path(self, project_name, project_path):
        """Resolve project name to a valid module path for cosmic-ray.

        This method attempts to find the module or package to mutate by
        checking if the project name corresponds to either a directory
        (package) or a Python file (module) within the project path.

        Parameters
        ----------
        project_name : str
            Name of the project/package to resolve.
        project_path : str or Path
            Path to the project directory.

        Returns
        -------
        str
            Resolved module path suitable for cosmic-ray configuration.
            Returns project_name if it's a package directory, or the
            filename if it's a module file.

        Raises
        ------
        ValueError
            If project_name doesn't correspond to either a package directory
            or a module file within project_path.
        """
        # lets try if this is a package
        full_path = pathlib.Path(project_path) / project_name
        if full_path.is_dir():
            return project_name

        # try as a module
        full_path = full_path.with_suffix(".py")
        if full_path.is_file():
            return full_path.name

        # fail
        raise ValueError(f"{project_name!r} can't be configure for cosmic-ray")

    def _write_conf(self, project_name, project_path, test_ids, config_file):
        """Write cosmic-ray configuration file for mutation testing.

        This method creates a TOML configuration file for cosmic-ray with
        the specified module path, test command, and other settings.

        Parameters
        ----------
        project_name : str
            Name of the project/package to mutate.
        project_path : str or Path
            Path to the project directory.
        test_ids : list[str]
            List of test IDs to run. If empty, all tests will be run.
        config_file : str or Path
            Path where the configuration file should be written.

        Notes
        -----
        The configuration includes:
        - module-path: Resolved path to the module/package to mutate
        - timeout: 50 seconds per mutation
        - test-command: pytest command with specified test IDs
        - distributor: local execution (no distributed testing)
        """
        test_command = "pytest " + " ".join(test_ids)
        module_path = self._resolve_module_path(project_name, project_path)
        config = {
            "module-path": module_path,
            "timeout": 50.0,
            "excluded-modules": [],
            "test-command": test_command,
            "distributor": {"name": "local"},
        }
        config_str = cray_config.serialize_config(config)
        with open(config_file, "w") as fp:
            fp.write(config_str)

    # ========================================================================
    # Public Methods
    # ========================================================================

    def get_mutations(self, project_path, project_name):
        """Run mutation testing and return the mutation score.

        Executes cosmic-ray to run all mutations against all tests and
        calculates the mutation score (percentage of mutants killed).

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run mutation testing on.
        project_name : str
            Name of the project/package to mutate.

        Returns
        -------
        SuiteRunResult
            Result containing:
            - value: float | None - Mutation score percentage (0-100)
            - command: str - The cosmic-ray command executed
            - status_code: int - Exit status from cosmic-ray
            - stdout: str - Standard output from cosmic-ray
            - stderr: str - Standard error from cosmic-ray
            - result: str - Additional mutation data
        """
        config_file = self._work_path / "global_run.toml"
        session_file = self._work_path / "global_run.sqlite"
        self._write_conf(project_name, project_path, [], config_file)

        # INIT THE MUTATION SUITE =============================================

        init_cmd, init_status, init_stdout, init_stderr = self._run(
            project_path,
            func=cray_cli.init.callback,
            args=(config_file, session_file, False),
        )

        # COLLECT THE NUMBER OF MUTATIONS =====================================

        xml_cmd, xml_status, xml_stdout, xml_stderr = self._run(
            project_path,
            func=cr_xml.report_xml.callback,
            args=(session_file,),
        )

        mutations = int(ET.fromstring(xml_stdout).get("tests"))

        # THE RETURN

        return self.pkg_result(
            value=mutations,
            command="\n\n".join([init_cmd, xml_cmd]),
            status_code=init_status + xml_status,
            stdout="\n\n".join([init_stdout, xml_stdout]),
            stderr="\n\n".join([init_stderr, xml_stderr]),
            result=xml_stdout,
        )

    def get_mutations_for_tests(self, project_path, project_name, tests_ids):
        """Run mutation testing with specific tests and return score.

        Executes cosmic-ray to run mutations against only the specified tests
        and calculates the mutation score.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run mutation testing on.
        project_name : str
            Name of the project/package to mutate.
        tests_ids : list[str]
            List of unique identifiers for tests to run against mutations
            (e.g., pytest node IDs).

        Returns
        -------
        SuiteRunResult
            Result containing:
            - value: float | None - Mutation score percentage (0-100)
            - command: str - The cosmic-ray command executed
            - status_code: int - Exit status from cosmic-ray
            - stdout: str - Standard output from cosmic-ray
            - stderr: str - Standard error from cosmic-ray
            - result: str - Additional mutation data

        Notes
        -----
        This method provides flexible mutation testing:
        - Single test ([test_id]): Measures isolated test mutation score
        - Multiple tests: Measures combined mutation score
        """
        # TODO: Implement cosmic-ray mutation testing for specific tests
        command, status, stdout, stderr = self._run(
            ["run", "config.toml"],
            project_path,
        )

        # Placeholder mutation score
        msr = None

        return self.pkg_result(
            value=msr,
            command=command,
            status_code=status,
            stdout=stdout,
            stderr=stderr,
            result="",
        )
