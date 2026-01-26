"""Yagua - Input/Output Operations.

This module provides functions for importing and exporting yagua work
directories, including archive creation, extraction, and format detection.
It centralizes all I/O logic to reduce code duplication and improve
maintainability.

Functions
---------
export_work_dir : function
    Export a work directory to an archive file.
import_archive : function
    Extract and validate an archive containing a yagua work directory.
read_dir : function
    Open an existing project work directory (returns Project).
read_archive : function
    Extract and open a project from an archive file (returns
    Project).
detect_archive_format : function
    Detect archive format from file extension.

Constants
---------
SUPPORTED_FORMATS : dict
    Mapping of file extensions to shutil archive format names.
"""

import shutil
import tempfile
from pathlib import Path

# ============================================================================
# CONSTANTS
# ============================================================================

#: Mapping of file extensions to shutil archive format names.
#: Supports both simple extensions (.zip, .tar) and compound extensions
#: (.tar.gz, .tar.bz2, .tar.xz).
SUPPORTED_FORMATS = {
    ".zip": "zip",
    ".tar": "tar",
    ".tgz": "gztar",
    ".tar.gz": "gztar",
    ".tbz2": "bztar",
    ".tar.bz2": "bztar",
    ".txz": "xztar",
    ".tar.xz": "xztar",
}


# ============================================================================
# PRIVATE FUNCTIONS
# ============================================================================


def _detect_archive_format(archive_path):
    """Detect archive format from file extension.

    This function examines the file extension(s) of the given path and
    determines the appropriate archive format for shutil operations.
    It handles both simple extensions (.zip) and compound extensions
    (.tar.gz, .tar.bz2, etc.).

    Parameters
    ----------
    archive_path : Path
        Path to the archive file.

    Returns
    -------
    tuple[str, Path]
        A tuple containing:
        - archive_format: str - The shutil format name (e.g., 'zip', 'gztar')
        - base_path: Path - Path without extension(s) for base name

    Raises
    ------
    ValueError
        If the file extension is not supported.

    Notes
    -----
    Supported formats:
    - .zip: ZIP archive
    - .tar: Uncompressed TAR archive
    - .tar.gz or .tgz: Gzipped TAR archive
    - .tar.bz2 or .tbz2: Bzip2 compressed TAR archive
    - .tar.xz or .txz: XZ compressed TAR archive
    """
    archive_path = Path(archive_path)
    suffix = archive_path.suffix.lower()

    # Check for compound extensions first (tar.gz, tar.bz2, tar.xz)
    if archive_path.suffixes:
        compound_suffix = "".join(archive_path.suffixes[-2:]).lower()
        if compound_suffix in SUPPORTED_FORMATS:
            archive_format = SUPPORTED_FORMATS[compound_suffix]
            # Remove both extensions for base name
            base_path = archive_path.with_suffix("").with_suffix("")
            return archive_format, base_path

    # Check simple extension
    if suffix in SUPPORTED_FORMATS:
        archive_format = SUPPORTED_FORMATS[suffix]
        # Remove single extension for base name
        base_path = archive_path.with_suffix("")
        return archive_format, base_path

    # Format not supported
    raise ValueError(
        f"Unsupported archive format: {suffix}. "
        f"Supported formats: {', '.join(SUPPORTED_FORMATS.keys())}"
    )


# ============================================================================
# PUBLIC FUNCTIONS - EXPORT
# ============================================================================


def export_work_dir(work_dir, output_path=None):
    """Export a work directory to an archive file.

    This function creates an archive file containing the complete work
    directory, including the yagua.db database and all temporary files.
    The archive format is automatically detected from the file extension.

    Parameters
    ----------
    work_dir : str or Path
        Path to the work directory to export.
    output_path : str or Path, optional
        Path where the archive will be created, including the desired
        extension (e.g., 'backup.zip', 'backup.tar.gz'). If not provided,
        defaults to '<work_dir_name>.zip' in the current directory.

    Returns
    -------
    Path
        Path to the created archive file.

    Raises
    ------
    ValueError
        If the archive format is not supported.
    FileNotFoundError
        If the work directory does not exist.

    Notes
    -----
    The archive preserves the complete directory structure and can be
    used to backup, share, or restore a yagua project.

    Supported formats:
    - .zip: ZIP archive
    - .tar: Uncompressed TAR archive
    - .tar.gz or .tgz: Gzipped TAR archive
    - .tar.bz2 or .tbz2: Bzip2 compressed TAR archive
    - .tar.xz or .txz: XZ compressed TAR archive

    See Also
    --------
    import_archive : Extract and validate an archive.
    """
    work_dir = Path(work_dir).resolve()

    if not work_dir.exists():
        raise FileNotFoundError(f"Work directory not found: {work_dir}")

    # Determine output path
    if output_path is None:
        output_path = Path.cwd() / f"{work_dir.name}.zip"
    else:
        output_path = Path(output_path)

    # Detect format and get base path
    archive_format, base_path = _detect_archive_format(output_path)

    # Create archive
    archive_path = shutil.make_archive(
        str(base_path),
        archive_format,
        work_dir.parent,
        work_dir.name,
    )

    return Path(archive_path)


# ============================================================================
# PUBLIC FUNCTIONS - IMPORT
# ============================================================================


def import_archive(archive_path, extract_to=None):
    """Extract and validate an archive containing a yagua work directory.

    This function extracts a work directory archive to a specified location
    (or a temporary directory if not specified) and validates that it
    contains a valid yagua.db file.

    Parameters
    ----------
    archive_path : str or Path
        Path to the archive file to extract.
    extract_to : str or Path, optional
        Directory where the archive should be extracted. If not provided,
        extracts to a temporary directory.

    Returns
    -------
    Path
        Path to the extracted work directory.

    Raises
    ------
    ValueError
        If the archive format is not supported or if the archive does not
        contain a valid yagua work directory.
    FileNotFoundError
        If the archive file does not exist.

    Notes
    -----
    The archive must contain a single directory with a yagua.db file inside.
    This is the standard format created by export_work_dir().

    If extract_to is None, the temporary directory will NOT be automatically
    cleaned up - the caller is responsible for cleanup.

    See Also
    --------
    export_work_dir : Export a work directory to an archive file.
    read_archive : Convenience function that also opens the project.
    """
    archive_path = Path(archive_path)

    if not archive_path.exists():
        raise FileNotFoundError(f"Archive file not found: {archive_path}")

    # Detect archive format
    archive_format, _ = _detect_archive_format(archive_path)

    # Determine extraction directory
    if extract_to is None:
        extract_to = Path(tempfile.mkdtemp(prefix="yagua_", suffix="_archive"))
    else:
        extract_to = Path(extract_to)
        extract_to.mkdir(parents=True, exist_ok=True)

    # Extract archive
    shutil.unpack_archive(str(archive_path), str(extract_to), archive_format)

    # Find the work directory (should be the only directory in extract_to)
    extracted_items = list(extract_to.iterdir())

    if len(extracted_items) == 0:
        raise ValueError(f"Archive is empty: {archive_path}")

    if len(extracted_items) == 1 and extracted_items[0].is_dir():
        work_dir = extracted_items[0]
    else:
        # If there are multiple items or a single file, assume extract_to
        # is the work directory
        work_dir = extract_to

    # Verify that yagua.db exists
    db_path = work_dir / "yagua.db"
    if not db_path.exists():
        raise ValueError(
            f"Archive does not contain a valid yagua work directory. "
            f"Missing yagua.db file in {work_dir}"
        )

    return work_dir


# ============================================================================
# PUBLIC FUNCTIONS - CONVENIENCE
# ============================================================================


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

    Notes
    -----
    This function is re-exported from yagua.__init__ for convenience.
    The actual imports are done at call time to avoid circular imports.

    See Also
    --------
    read_archive : Extract and open a project from an archive file.
    """
    from . import project as project_module

    return project_module.from_work_dir(path)


def read_archive(archive_path):
    """Extract and open a project from an archive file.

    This is a convenience function that extracts a work directory archive
    (created with the export command or export_work_dir()) to a temporary
    directory and opens the project for use. The temporary directory is
    automatically cleaned up when the Project instance is closed or
    when the Python process exits.

    Parameters
    ----------
    archive_path : str or Path
        Path to an archive file containing a yagua work directory.
        Supported formats: .zip, .tar, .tar.gz (.tgz), .tar.bz2 (.tbz2),
        .tar.xz (.txz).

    Returns
    -------
    Project
        Project instance connected to the extracted work directory
        in a temporary location.

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
    data, use export_work_dir() to create a new archive before closing
    the project.

    The archive must contain a single directory with a yagua.db file inside.
    This is the standard format created by export_work_dir().

    See Also
    --------
    read_dir : Open an existing project work directory.
    import_archive : Lower-level function for extracting archives.
    export_work_dir : Export work directory to an archive file.
    """
    from . import project as project_module

    try:
        work_dir = import_archive(archive_path)
        return project_module.from_work_dir(work_dir)
    except Exception:
        # Clean up temp directory if opening fails
        work_dir_parent = work_dir.parent if "work_dir" in locals() else None
        if work_dir_parent and work_dir_parent.name.startswith("yagua_"):
            shutil.rmtree(work_dir_parent, ignore_errors=True)
        raise
