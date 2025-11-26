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
from unittest import mock
import json

from cosmic_ray import config as cray_config
from cosmic_ray import cli as cray_cli

from .abc import MutationSuiteABC


# ============================================================================
# COSMIC RAY SUITE
# ============================================================================


class ExitCalled(Exception):
    pass


class _ExitCapture:

    def __call__(self, value):
        self.value = value
        raise ExitCalled()


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
        func = func.__name__
        args = ", ".join(map(repr, args))
        kwargs = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        kwargs = f", {kwargs}" if kwargs else ""
        return f"{func}({args}, {kwargs})"

    def _run(self, project_path, func, args=None, kwargs=None):

        args = args or ()
        kwargs = kwargs or {}
        stdout, stderr = io.StringIO(), io.StringIO()
        full_cmd = self._render_full_cmd(func, args, kwargs)

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

        return (full_cmd, status, stdout.getvalue(), stderr.getvalue())

    def _resolve_module_path(self, project_name, project_path):
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

        run_outputs = []

        outputs = self._run(
            project_path,
            func=cray_cli.init.callback,
            args=(config_file, session_file, False),
        )

        run_outputs.append(outputs)

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
