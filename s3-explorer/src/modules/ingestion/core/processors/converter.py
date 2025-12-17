"""Document converter implementations."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from src.modules.ingestion.core.models import FileContext, FileStatus
from src.modules.ingestion.core.processors.base import FileProcessor
from src.shared._logging import get_logger

logger = get_logger(__name__)


class DocxToPdfConverter(FileProcessor):
    """Convert DOCX/DOC files to PDF using LibreOffice.

    This implementation uses LibreOffice/soffice for conversion,
    which is more reliable than python libraries for complex documents.
    """

    def __init__(self, libreoffice_path: str = "soffice"):
        """Initialize converter.

        Args:
            libreoffice_path: Path to LibreOffice executable (default: 'soffice')
        """
        self.libreoffice_path = self._resolve_libreoffice_path(libreoffice_path)

    def _resolve_libreoffice_path(self, path: str) -> str:
        """Resolve the correct LibreOffice executable path.

        On Windows, we prefer 'soffice.com' over 'soffice.exe' for CLI operations
        as it handles stdout/stderr correctly and avoids some window popup issues.
        """
        if os.name != "nt":
            return path

        if path != "soffice" and os.path.isabs(path):
            return path

        candidates = [
            shutil.which("soffice.com"),
            r"C:\Program Files\LibreOffice\program\soffice.com",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.com",
        ]

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                logger.info(f"Resolved LibreOffice path to: {candidate}")
                return candidate

        return path

    def can_process(self, file_context: FileContext) -> bool:
        """Check if this processor can handle DOCX/DOC files.

        Args:
            file_context: File to check

        Returns:
            True if file is DOCX or DOC
        """
        return file_context.file_type in [
            "docx",
            "doc",
        ] or file_context.source_path.lower().endswith((".docx", ".doc"))

    def _get_subprocess_kwargs(self) -> Dict[str, Any]:
        """Get subprocess arguments to hide window on Windows."""
        kwargs = {}
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = startupinfo
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        return kwargs

    def process(self, file_context: FileContext, output_dir: Path) -> List[FileContext]:
        """Convert DOCX/DOC to PDF.

        Args:
            file_context: File to convert
            output_dir: Directory to store output PDF

        Returns:
            List with single converted FileContext
        """
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            # Determine output filename
            input_path = Path(file_context.local_path)
            output_filename = input_path.stem + ".pdf"
            output_path = output_dir / output_filename

            # Use LibreOffice for conversion
            cmd = [
                self.libreoffice_path,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(input_path),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                **self._get_subprocess_kwargs(),
            )

            if result.returncode != 0:
                error_msg = f"LibreOffice conversion failed: {result.stderr}"
                logger.error(error_msg)
                file_context.status = FileStatus.FAILED
                file_context.error_message = error_msg
                return [file_context]

            # Create new context for converted file
            converted_context = FileContext(
                source_path=file_context.source_path,
                local_path=str(output_path),
                file_type="pdf",
                status=FileStatus.CONVERTED,
                parent_folder=file_context.parent_folder,
            )

            logger.info(f"Successfully converted {input_path.name} to PDF")
            return [converted_context]

        except subprocess.TimeoutExpired:
            error_msg = "Conversion timeout (exceeded 5 minutes)"
            logger.error(error_msg)
            file_context.status = FileStatus.FAILED
            file_context.error_message = error_msg
            return [file_context]
        except Exception as e:
            error_msg = f"Error during conversion: {str(e)}"
            logger.error(error_msg)
            file_context.status = FileStatus.FAILED
            file_context.error_message = error_msg
            return [file_context]

    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions.

        Returns:
            List of extensions
        """
        return [".docx", ".doc"]

    def is_libreoffice_available(self) -> bool:
        """Check if LibreOffice is available.

        Returns:
            True if LibreOffice is available
        """
        try:
            # Add input=b'\n' to handle cases where it pauses with "Press Enter..."
            result = subprocess.run(
                [self.libreoffice_path, "--version"],
                capture_output=True,
                timeout=30,
                input=b"\n",
                **self._get_subprocess_kwargs(),
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Error checking LibreOffice availability: {e}")
            return False


class PypandocConverter(FileProcessor):
    """Alternative converter using pypandoc (fallback if LibreOffice not available).

    Note: pypandoc requires pandoc to be installed on the system.
    """

    def __init__(self):
        """Initialize pypandoc converter."""
        try:
            import pypandoc

            self.pypandoc = pypandoc
            self.available = True
        except ImportError:
            logger.warning("pypandoc not available, converter will not work")
            self.available = False

    def can_process(self, file_context: FileContext) -> bool:
        """Check if this processor can handle DOCX files.

        Args:
            file_context: File to check

        Returns:
            True if file is DOCX and pypandoc is available
        """
        return self.available and (
            file_context.file_type == "docx"
            or file_context.source_path.lower().endswith(".docx")
        )

    def process(self, file_context: FileContext, output_dir: Path) -> List[FileContext]:
        """Convert DOCX to PDF using pypandoc.

        Args:
            file_context: File to convert
            output_dir: Directory to store output PDF

        Returns:
            List with single converted FileContext
        """
        if not self.available:
            error_msg = "pypandoc not available"
            logger.error(error_msg)
            file_context.status = FileStatus.FAILED
            file_context.error_message = error_msg
            return [file_context]

        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            input_path = Path(file_context.local_path)
            output_filename = input_path.stem + ".pdf"
            output_path = output_dir / output_filename

            logger.info(f"Converting {input_path.name} to PDF using pypandoc...")

            self.pypandoc.convert_file(
                str(input_path),
                "pdf",
                outputfile=str(output_path),
                extra_args=["--pdf-engine=xelatex"],
            )

            converted_context = FileContext(
                source_path=file_context.source_path,
                local_path=str(output_path),
                file_type="pdf",
                status=FileStatus.CONVERTED,
                parent_folder=file_context.parent_folder,
            )

            logger.info(f"Successfully converted {input_path.name} to PDF")
            return [converted_context]

        except Exception as e:
            error_msg = f"Error during pypandoc conversion: {str(e)}"
            logger.error(error_msg)
            file_context.status = FileStatus.FAILED
            file_context.error_message = error_msg
            return [file_context]

    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions.

        Returns:
            List of extensions
        """
        return [".docx"]
