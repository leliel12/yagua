"""Yagua - Cosmic Ray Suite Handler.

This module provides a mutation suite handler for cosmic-ray-based projects,
implementing the MutationSuiteABC interface using subprocess calls to the
cosmic-ray CLI commands.

Classes
-------
CosmicRaySuite : class
    Mutation suite handler using cosmic-ray CLI via subprocess.

Implementation Details
----------------------
This implementation uses:
- subprocess.run() for executing cosmic-ray CLI commands
- SQLite database for mutation results storage
- Hash-based temporary file naming for deterministic identification
- Direct command execution without Python API imports

Key Features
------------
- Better isolation from cosmic-ray API changes
- Command-line based execution (more stable)
- Hash-based file naming for session management
- Complete audit trail (captures command, stdout, stderr, and results)

Dependencies
------------
- cosmic-ray: Must be installed and available in system PATH
"""

import hashlib
import pathlib
import subprocess
import xml.etree.ElementTree as ET

from .abc import MutationSuiteABC

# ============================================================================
# COSMIC RAY SUITE
# ============================================================================


class CosmicRaySuite(MutationSuiteABC):
    """Mutation suite handler for cosmic-ray-based projects.

    This class implements the MutationSuiteABC interface for projects using
    cosmic-ray for mutation testing, executing cosmic-ray as an external
    command via subprocess rather than using its Python API.

    This implementation invokes cosmic-ray as a system command, making it
    more isolated from cosmic-ray internal API changes and potentially more
    stable across different cosmic-ray versions.

    Attributes
    ----------
    _work_path : pathlib.Path
        Working directory for storing mutation databases and config files.
        Files are named using hashes for deterministic identification.
    _mutation_timeout : float
        Timeout in seconds for each mutation test.

    Notes
    -----
    This implementation requires cosmic-ray to be installed in the
    environment and the 'cosmic-ray' command must be available in the
    system PATH.
    """

    # ========================================================================
    # Constructor
    # ========================================================================

    def __init__(self, work_path, mutation_timeout=50.0):
        """Initialize CosmicRaySuite with working directory.

        Parameters
        ----------
        work_path : str or Path
            Path to the working directory where intermediate files
            (e.g., mutation databases, configuration files) will be stored.
        mutation_timeout : float, optional
            Timeout in seconds for each mutation test. Default is 50.0.
        """
        self._verbose = False
        self._work_path = pathlib.Path(work_path) / "yagua_cray"
        self._work_path.mkdir(parents=True, exist_ok=True)
        self._mutation_timeout = float(mutation_timeout)

    # ========================================================================
    # Private Methods
    # ========================================================================

    def _run(self, cmd, project_path):
        """Run cosmic-ray command using subprocess.

        This internal method executes cosmic-ray as an external command,
        capturing output and changing to the project directory.

        Parameters
        ----------
        cmd : list[str]
            Command arguments to pass to cosmic-ray
            (e.g., ['cosmic-ray', 'init', 'config.toml', 'session.sqlite']).
        project_path : str or Path
            Working directory for cosmic-ray execution. Cosmic-ray will run
            as if executed from this directory.

        Returns
        -------
        command : str
            Space-joined command string for audit logging.
        status_code : int
            Exit status code from cosmic-ray execution.
        stdout : str
            Captured standard output from cosmic-ray execution.
        stderr : str
            Captured standard error from cosmic-ray execution.

        Notes
        -----
        This method uses subprocess.run() to execute the command with:
        1. cwd set to the project directory
        2. stdout and stderr captured as text
        3. Shell disabled for security
        """
        full_cmd = " ".join(cmd)
        if self._verbose:
            print(f"[RUN] {project_path} >> {full_cmd!r}")

        result = subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
        )

        return (full_cmd, result.returncode, result.stdout, result.stderr)

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
        # Try if this is a package
        full_path = pathlib.Path(project_path) / project_name
        if full_path.is_dir():
            return project_name

        # Try as a module
        full_path = full_path.with_suffix(".py")
        if full_path.is_file():
            return full_path.name

        # Fail
        raise ValueError(
            f"{project_name!r} can't be configured for cosmic-ray"
        )

    def _write_conf(
        self, project_name, project_path, test_command, config_file
    ):
        """Write cosmic-ray configuration file for mutation testing.

        This method creates a TOML configuration file for cosmic-ray with
        the specified module path, test command, and timeout settings.

        Parameters
        ----------
        project_name : str
            Name of the project/package to mutate.
        project_path : str or Path
            Path to the project directory.
        test_command : str
            Test command to run (e.g., "pytest" or "pytest test_file.py").
        config_file : str or Path
            Path where the configuration file should be written.

        Notes
        -----
        The configuration includes:
        - module-path: Resolved path to the module/package to mutate
        - timeout: Configured mutation timeout
        - test-command: Command to run tests
        - distributor: local execution (no distributed testing)

        The TOML file is written manually to avoid dependency on
        cosmic-ray's config module.
        """
        module_path = self._resolve_module_path(project_name, project_path)

        # Write TOML config manually
        config_content = f"""[cosmic-ray]
module-path = "{module_path}"
timeout = {self._mutation_timeout}
excluded-modules = []
test-command = "{test_command}"

[cosmic-ray.distributor]
name = "local"
"""
        with open(config_file, "w") as fp:
            fp.write(config_content)

    def _init_suite(
        self, *, project_path, project_name, tag, test_command, force
    ):
        """Initialize cosmic-ray session with config and database files.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory.
        project_name : str
            Name of the project/package to mutate.
        tag : str
            Unique tag for this session (used in filenames).
        test_command : str
            Test command to run.
        force : bool
            Force re-initialization even if files exist.

        Returns
        -------
        config_file : pathlib.Path
            Path to the configuration file.
        session_file : pathlib.Path
            Path to the session database file.
        init_output : tuple
            Tuple of (command, status, stdout, stderr) from init command.
        """
        config_file = self._work_path / f"{tag}.toml"
        session_file = self._work_path / f"{tag}.sqlite"

        if force or not config_file.exists():
            self._write_conf(
                project_name, project_path, test_command, config_file
            )

        if force or not session_file.exists():
            cmd = [
                "cosmic-ray",
                "init",
                str(config_file),
                str(session_file),
            ]
            init_output = self._run(cmd, project_path)
        else:
            init_output = ("", 0, "", "")

        return config_file, session_file, init_output

    def hash_tests_ids(self, tests_ids):
        """Generate MD5 hash from sorted test IDs.

        This method creates a unique hash for a set of test IDs, useful for
        generating unique session identifiers when running mutations with
        specific test subsets.

        Parameters
        ----------
        tests_ids : list[str]
            List of test identifiers to hash.

        Returns
        -------
        str
            Hexadecimal digest of the MD5 hash for the concatenated, sorted
            test IDs.

        Notes
        -----
        Test IDs are sorted before hashing to ensure consistent hashes
        regardless of input order.
        """
        all_ids = "".join(sorted(tests_ids))
        md5 = hashlib.md5(all_ids.encode("utf8"))
        return md5.hexdigest()

    # ========================================================================
    # Public Methods
    # ========================================================================

    def get_mutants(self, project_path, project_name, force):
        """Run mutation initialization and return the number of mutants.

        Executes cosmic-ray to initialize the mutation session and count
        the total number of mutants that will be generated for the project.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run mutation testing on.
        project_name : str
            Name of the project/package to mutate.
        force : bool
            Force re-initialization even if session exists.

        Returns
        -------
        SuiteRunResult
            Result containing:
            - value: int | None - Number of mutants generated
            - command: str - The cosmic-ray commands executed
            - status_code: int - Exit status from cosmic-ray
            - stdout: str - Standard output from cosmic-ray
            - stderr: str - Standard error from cosmic-ray
            - result: str - XML report with mutation data
        """
        # INIT SUITE
        _, session_file, init_output = self._init_suite(
            project_path=project_path,
            project_name=project_name,
            tag="get_mutants",
            test_command="pytest",
            force=force,
        )
        init_cmd, init_status, init_stdout, init_stderr = init_output

        # GET MUTATION COUNT FROM XML REPORT
        xml_cmd = ["cr-xml", str(session_file)]
        xml_cmd_str, xml_status, xml_stdout, xml_stderr = self._run(
            xml_cmd, project_path
        )

        # Parse XML to get mutation count
        # cosmic-ray report outputs XML with test count
        try:
            mutations = int(ET.fromstring(xml_stdout).get("tests", 0))
        except (ET.ParseError, ValueError, TypeError):
            mutations = 0

        # THE RETURN
        return self.pkg_result(
            value=mutations,
            command="\n\n".join([init_cmd, xml_cmd_str]),
            status_code=init_status + xml_status,
            stdout="\n\n".join([init_stdout, xml_stdout]),
            stderr="\n\n".join([init_stderr, xml_stderr]),
            result=xml_stdout,
        )

    def get_survival_rate(self, project_path, project_name, force):
        """Execute mutation testing and return the survival rate.

        This method runs all mutation tests against the test suite using
        cosmic-ray and calculates the mutation survival rate.

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
        SuiteRunResult
            Result containing:
            - value: float - Mutation survival rate percentage (0-100)
            - command: str - The cosmic-ray commands executed
            - status_code: int - Combined exit status from all commands
            - stdout: str - Combined standard output
            - stderr: str - Combined standard error
            - result: str - Survival rate output from cosmic-ray

        Notes
        -----
        This method performs three steps:
        1. Initialize mutation session (if needed or forced)
        2. Execute all mutations against the test suite
        3. Calculate and return the survival rate
        """
        # INIT SUITE
        config_file, session_file, init_output = self._init_suite(
            project_path=project_path,
            project_name=project_name,
            tag="get_survival_rate",
            test_command="pytest",
            force=force,
        )
        init_cmd, init_status, init_stdout, init_stderr = init_output

        # EXECUTE MUTATIONS
        exec_cmd = ["cosmic-ray", "exec", str(config_file), str(session_file)]
        (exec_cmd_str, exec_status, exec_stdout, exec_stderr) = self._run(
            exec_cmd, project_path
        )

        # GET SURVIVAL RATE
        sr_cmd = ["cr-rate", str(session_file)]
        sr_cmd_str, sr_status, sr_stdout, sr_stderr = self._run(
            sr_cmd, project_path
        )

        # Parse survival rate from output
        try:
            survival_rate = float(sr_stdout.strip())
        except (ValueError, AttributeError):
            survival_rate = 0.0

        # THE RETURN
        return self.pkg_result(
            value=survival_rate,
            command="\n\n".join([init_cmd, exec_cmd_str, sr_cmd_str]),
            status_code=init_status + exec_status + sr_status,
            stdout="\n\n".join([init_stdout, exec_stdout, sr_stdout]),
            stderr="\n\n".join([init_stderr, exec_stderr, sr_stderr]),
            result=sr_stdout,
        )

    def get_survival_rate_for_tests(
        self, project_path, project_name, tests_ids, force
    ):
        """Run specific test(s) with mutations and return survival rate.

        This method runs specified tests against all mutations using
        cosmic-ray to measure their combined mutation detection capability.
        Uses a hash of test IDs to create unique session files for different
        test combinations.

        Parameters
        ----------
        project_path : str or Path
            Path to the project directory to run mutation testing on.
        project_name : str
            Name of the project/package to mutate.
        tests_ids : list[str]
            List of unique identifiers for tests to run (e.g., pytest node
            IDs). Can be a single-item list for isolated test analysis, or
            multiple items for combined analysis.
        force : bool
            Force re-execution of mutations even if already run.

        Returns
        -------
        SuiteRunResult
            Result containing:
            - value: float - Mutation survival rate percentage (0-100)
            - command: str - The cosmic-ray commands executed
            - status_code: int - Combined exit status from all commands
            - stdout: str - Combined standard output
            - stderr: str - Combined standard error
            - result: str - Survival rate output from cosmic-ray

        Notes
        -----
        This method performs three steps:
        1. Initialize mutation session with test-specific configuration
        2. Execute mutations against specified tests only
        3. Calculate and return the survival rate

        The test_ids are used to configure cosmic-ray to run only those
        specific tests, enabling per-test or subset mutation analysis.
        """
        # INIT SUITE
        tests_hash = self.hash_tests_ids(tests_ids)
        test_command = "pytest " + " ".join(tests_ids)

        config_file, session_file, init_output = self._init_suite(
            project_path=project_path,
            project_name=project_name,
            tag=f"get_survival_rate_for_tests_{tests_hash}",
            test_command=test_command,
            force=force,
        )
        init_cmd, init_status, init_stdout, init_stderr = init_output

        # EXECUTE MUTATIONS
        exec_cmd = ["cosmic-ray", "exec", str(config_file), str(session_file)]
        (exec_cmd_str, exec_status, exec_stdout, exec_stderr) = self._run(
            exec_cmd, project_path
        )

        # GET SURVIVAL RATE
        sr_cmd = ["cr-rate", str(session_file)]
        sr_cmd_str, sr_status, sr_stdout, sr_stderr = self._run(
            sr_cmd, project_path
        )

        # Parse survival rate from output
        try:
            survival_rate = float(sr_stdout.strip())
        except (ValueError, AttributeError):
            survival_rate = 0.0

        # THE RETURN
        return self.pkg_result(
            value=survival_rate,
            command="\n\n".join([init_cmd, exec_cmd_str, sr_cmd_str]),
            status_code=init_status + exec_status + sr_status,
            stdout="\n\n".join([init_stdout, exec_stdout, sr_stdout]),
            stderr="\n\n".join([init_stderr, exec_stderr, sr_stderr]),
            result=sr_stdout,
        )
