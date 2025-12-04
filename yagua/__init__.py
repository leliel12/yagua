"""Yagua - Tool for collecting and managing test information.

Yagua is a Python package for collecting and managing test information from
pytest-based projects. It provides tools to discover tests, collect coverage
metrics, and analyze test redundancy and uniqueness.

Main Components
---------------
main : function
    CLI entry point for the yagua command-line tool.
Project : class
    Main class for managing project databases and test information.
PytestSuite : class
    Test suite handler for pytest-based projects.
TestSuiteABC : class
    Abstract base class for implementing test suite handlers.
read_dir : function
    Convenience function to open an existing project work directory.
read_archive : function
    Convenience function to extract and open a project from an archive file.
"""

import shutil
import tempfile
from pathlib import Path

from .cli import main
from .project import Project
from .testsuites import PytestSuite, TestSuiteABC

__all__ = [
    "main",
    "Project",
    "PytestSuite",
    "TestSuiteABC",
    "read_dir",
    "read_archive",
]


def read_dir(path):
    """Open an existing project work directory.

    This is a convenience function that creates a Project instance
    from an existing work directory containing a yagua.db file.

    Parameters
    ----------
    path : str or Path
        Path to an existing work directory.

    Returns
    -------
    Project
        Project instance connected to the specified work directory.

    See Also
    --------
    Project : Main project management class.
    Project.from_project_info : Create a new project with metadata.
    read_archive : Extract and open a project from an archive file.
    """
    return Project(path)


def read_archive(archive_path):
    """Extract and open a project from an archive file.

    This is a convenience function that extracts a work directory archive
    (created with the export command or Project.export_work_dir()) to a
    temporary directory and opens the project for use. The temporary
    directory is automatically cleaned up when the Project instance is
    closed or when the Python process exits.

    Parameters
    ----------
    archive_path : str or Path
        Path to an archive file containing a yagua work directory.
        Supported formats: .zip, .tar, .tar.gz (.tgz), .tar.bz2 (.tbz2),
        .tar.xz (.txz).

    Returns
    -------
    Project
        Project instance connected to the extracted work directory in a
        temporary location.

    Raises
    ------
    ValueError
        If the archive format is not supported or if the archive does not
        contain a valid yagua work directory.
    FileNotFoundError
        If the archive file does not exist.

    Notes
    -----
    The extracted work directory is placed in a temporary directory that
    will be automatically cleaned up. If you need to preserve the extracted
    data, use Project.export_work_dir() to create a new archive before
    closing the project.

    The archive must contain a single directory with a yagua.db file inside.
    This is the standard format created by the export command.

    See Also
    --------
    Project : Main project management class.
    Project.export_work_dir : Export work directory to an archive file.
    read_dir : Open an existing project work directory.

    Examples
    --------
    Open a project from an exported archive:

        >>> proj = read_archive("my_project.zip")
        >>> tests_df = proj.get_tests_dataframe()
        >>> proj.close()

    Use as a context manager for automatic cleanup:

        >>> with read_archive("my_project.tar.gz") as proj:
        ...     print(proj.name)
        ...     print(proj.coverage)
    """
    archive_path = Path(archive_path)

    if not archive_path.exists():
        raise FileNotFoundError(f"Archive file not found: {archive_path}")

    # Determine archive format from extension
    suffix = archive_path.suffix.lower()
    format_map = {
        ".zip": "zip",
        ".tar": "tar",
        ".tgz": "gztar",
        ".gz": "gztar",
        ".tbz2": "bztar",
        ".bz2": "bztar",
        ".txz": "xztar",
        ".xz": "xztar",
    }

    # Check for compound extensions (tar.gz, tar.bz2, tar.xz)
    archive_format = None
    if archive_path.suffixes:
        compound_suffix = "".join(archive_path.suffixes[-2:]).lower()
        compound_map = {
            ".tar.gz": "gztar",
            ".tar.bz2": "bztar",
            ".tar.xz": "xztar",
        }
        if compound_suffix in compound_map:
            archive_format = compound_map[compound_suffix]

    if archive_format is None:
        archive_format = format_map.get(suffix)

    if archive_format is None:
        raise ValueError(
            f"Unsupported archive format: {suffix}. "
            f"Supported formats: .zip, .tar, .tar.gz, .tgz, "
            f".tar.bz2, .tbz2, .tar.xz, .txz"
        )

    # Create temporary directory for extraction
    temp_dir = Path(tempfile.mkdtemp(prefix="yagua_", suffix="_archive"))

    try:
        # Extract archive
        shutil.unpack_archive(str(archive_path), str(temp_dir), archive_format)

        # Find the work directory (should be the only directory in temp_dir)
        extracted_items = list(temp_dir.iterdir())

        if len(extracted_items) == 0:
            raise ValueError(f"Archive is empty: {archive_path}")

        if len(extracted_items) == 1 and extracted_items[0].is_dir():
            work_dir = extracted_items[0]
        else:
            # If there are multiple items or a single file, assume temp_dir
            # is the work directory
            work_dir = temp_dir

        # Verify that yagua.db exists
        db_path = work_dir / "yagua.db"
        if not db_path.exists():
            raise ValueError(
                f"Archive does not contain a valid yagua work directory. "
                f"Missing yagua.db file in {work_dir}"
            )

        # Open and return the project
        return Project(work_dir)

    except Exception:
        # Clean up temp directory if opening fails
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
