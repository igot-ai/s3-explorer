"""Archive extractor implementations using patool.

Reference: https://github.com/wummel/patool
"""

from pathlib import Path
from typing import List

from src.modules.ingestion.core.models import FileContext, FileStatus
from src.modules.ingestion.core.processors.base import FileProcessor
from src.shared._logging import get_logger

logger = get_logger(__name__)


class ArchiveExtractor(FileProcessor):
    """Extract files from archives using patool library.

    Supports all formats from patool: 7z, ACE, ADF, ALZIP, APE, AR, ARC, ARJ,
    BZIP2, BZIP3, CAB, CHM, COMPRESS, CPIO, DEB, DMS, FLAC, FREEARC, GZIP,
    ISO, LRZIP, LZH, LZIP, LZMA, LZOP, RPM, RAR, RZIP, SHN, TAR, UDF, XZ,
    ZIP, ZOO, and ZSTANDARD.

    Install with: pip install patool
    Reference: https://github.com/wummel/patool
    """

    # All supported extensions from patool
    SUPPORTED_FORMATS = {
        "7z",
        "ace",
        "adf",
        "alz",
        "ape",
        "a",
        "arc",
        "arj",
        "bz2",
        "bz3",
        "cab",
        "chm",
        "Z",
        "cpio",
        "deb",
        "dms",
        "flac",
        "gz",
        "iso",
        "lrz",
        "lha",
        "lzh",
        "lz",
        "lzma",
        "lzo",
        "rpm",
        "rar",
        "rz",
        "shn",
        "tar",
        "udf",
        "xz",
        "zip",
        "jar",
        "zoo",
        "zst",
        # Compound formats
        "tar.gz",
        "tgz",
        "tar.bz2",
        "tbz2",
        "tar.xz",
        "txz",
        "tar.lz",
        "tar.lzma",
        "tar.zst",
    }

    def __init__(self, verbosity: int = -1):
        """Initialize archive extractor.

        Args:
            verbosity: Verbosity level for patool (-1 = quiet, 0 = normal, 1 = verbose)
        """
        self.verbosity = verbosity
        try:
            import patoolib

            self.patoolib = patoolib
            self.available = True
            logger.debug("patool library loaded successfully")
        except ImportError:
            logger.warning("patool not available. Install with: pip install patool")
            self.available = False

    def can_process(self, file_context: FileContext) -> bool:
        """Check if this processor can handle archive files.

        Uses patool's is_archive() for accurate detection.

        Args:
            file_context: File to check

        Returns:
            True if file is a supported archive format
        """
        if not self.available:
            return False

        # Check by file extension first (fast)
        file_ext = file_context.file_type.lower()
        if file_ext in self.SUPPORTED_FORMATS:
            return True

        # Check compound extensions like .tar.gz
        if file_context.local_path:
            file_path = Path(file_context.local_path)
            # Check for .tar.gz, .tar.bz2, etc.
            if len(file_path.suffixes) >= 2:
                compound_ext = "".join(file_path.suffixes[-2:]).lstrip(".")
                if compound_ext in self.SUPPORTED_FORMATS:
                    return True

        # Use patool's is_archive() for final check if file exists
        if file_context.local_path and Path(file_context.local_path).exists():
            try:
                return self.patoolib.is_archive(file_context.local_path)
            except Exception:
                pass

        return False

    def process(self, file_context: FileContext, output_dir: Path) -> List[FileContext]:
        """Extract files from archive using patool.

        Args:
            file_context: Archive file to extract
            output_dir: Directory to extract files to

        Returns:
            List of FileContext objects for extracted files
        """
        if not self.available:
            error_msg = "patool not available for archive extraction"
            logger.error(error_msg)
            file_context.status = FileStatus.FAILED
            file_context.error_message = error_msg
            return [file_context]

        try:
            # Create extraction directory
            archive_name = Path(file_context.source_path).stem
            extract_dir = output_dir / archive_name
            extract_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Extracting archive: {file_context.source_path}")

            # Extract archive using patool
            # API: patoolib.extract_archive(archive, outdir=None, verbosity=0)
            self.patoolib.extract_archive(
                file_context.local_path,
                outdir=str(extract_dir),
                verbosity=self.verbosity,
            )

            # Collect all extracted files
            extracted_files = []
            for file_path in extract_dir.rglob("*"):
                if file_path.is_file():
                    # Create FileContext for each extracted file
                    relative_path = file_path.relative_to(extract_dir)
                    file_type = file_path.suffix.lower().lstrip(".")

                    extracted_context = FileContext(
                        source_path=f"{file_context.source_path}/{relative_path}",
                        local_path=str(file_path),
                        file_type=file_type,
                        status=FileStatus.PENDING,
                        parent_folder=file_context.parent_folder,
                    )
                    extracted_files.append(extracted_context)

            logger.info(
                f"Extracted {len(extracted_files)} files from {file_context.source_path}"
            )
            return extracted_files

        except Exception as e:
            error_msg = f"Error extracting archive: {str(e)}"
            logger.error(error_msg)
            file_context.status = FileStatus.FAILED
            file_context.error_message = error_msg
            return [file_context]

    def test_archive(self, file_path: str) -> bool:
        """Test archive integrity using patool.

        Args:
            file_path: Path to archive file

        Returns:
            True if archive is valid, False otherwise
        """
        if not self.available:
            return False

        try:
            # API: patoolib.test_archive(archive, verbosity=0)
            self.patoolib.test_archive(file_path, verbosity=self.verbosity)
            return True
        except Exception as e:
            logger.error(f"Archive test failed: {str(e)}")
            return False

    def get_supported_extensions(self) -> List[str]:
        """Get supported archive formats.

        Returns all formats supported by patool.

        Returns:
            List of extensions
        """
        # Return with dots for consistency
        return [f".{ext}" for ext in sorted(self.SUPPORTED_FORMATS)]


class SimpleZipExtractor(FileProcessor):
    """Simple ZIP extractor using Python's built-in zipfile module.

    Fallback if patool is not available.
    """

    def can_process(self, file_context: FileContext) -> bool:
        """Check if this processor can handle ZIP files.

        Args:
            file_context: File to check

        Returns:
            True if file is ZIP
        """
        return (
            file_context.file_type == "zip"
            or file_context.source_path.lower().endswith(".zip")
        )

    def process(self, file_context: FileContext, output_dir: Path) -> List[FileContext]:
        """Extract files from ZIP archive.

        Args:
            file_context: ZIP file to extract
            output_dir: Directory to extract files to

        Returns:
            List of FileContext objects for extracted files
        """
        import zipfile

        try:
            # Create extraction directory
            archive_name = Path(file_context.source_path).stem
            extract_dir = output_dir / archive_name
            extract_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Extracting ZIP: {file_context.source_path}...")

            # Extract ZIP file
            with zipfile.ZipFile(file_context.local_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

            # Collect all extracted files
            extracted_files = []
            for file_path in extract_dir.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(extract_dir)
                    file_type = file_path.suffix.lower().lstrip(".")

                    extracted_context = FileContext(
                        source_path=f"{file_context.source_path}/{relative_path}",
                        local_path=str(file_path),
                        file_type=file_type,
                        status=FileStatus.PENDING,
                        parent_folder=file_context.parent_folder,
                    )
                    extracted_files.append(extracted_context)

            logger.info(f"Extracted {len(extracted_files)} files from ZIP")
            return extracted_files

        except Exception as e:
            error_msg = f"Error extracting ZIP: {str(e)}"
            logger.error(error_msg)
            file_context.status = FileStatus.FAILED
            file_context.error_message = error_msg
            return [file_context]

    def get_supported_extensions(self) -> List[str]:
        """Get supported extensions.

        Returns:
            List of extensions
        """
        return [".zip"]
