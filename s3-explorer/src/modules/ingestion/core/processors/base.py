"""Abstract base class for file processors."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from src.modules.ingestion.core.models import FileContext, FileStatus
from src.shared._logging import get_logger

logger = get_logger(__name__)


class FileProcessor(ABC):
    """Abstract interface for file processing operations.

    Processors handle conversion (e.g., DOCX to PDF) and extraction (e.g., ZIP/RAR).
    """

    @abstractmethod
    def can_process(self, file_context: FileContext) -> bool:
        """Check if this processor can handle the given file type.

        Args:
            file_context: File to check

        Returns:
            True if this processor can handle the file
        """
        pass

    @abstractmethod
    def process(self, file_context: FileContext, output_dir: Path) -> List[FileContext]:
        """Process the file and return resulting file contexts.

        Args:
            file_context: File to process
            output_dir: Directory to store output files

        Returns:
            List of FileContext objects (1 for converters, multiple for extractors)
        """
        pass

    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions.

        Returns:
            List of extensions (e.g., ['.docx', '.doc'])
        """
        pass


class FileProcessorChain:
    """Chain of Responsibility pattern for file processing.

    Routes files to the appropriate processor based on file type.
    """

    def __init__(self, processors: List[FileProcessor]):
        """Initialize processor chain.

        Args:
            processors: List of processors to chain
        """
        self.processors = processors

    def process(self, file_context: FileContext, output_dir: Path) -> List[FileContext]:
        """Route file to appropriate processor recursively.

        Args:
            file_context: File to process
            output_dir: Directory for output files

        Returns:
            List of processed FileContext objects
        """
        # Try each processor in order
        for processor in self.processors:
            if processor.can_process(file_context):
                logger.info(
                    f"Processing {file_context.source_path} with {processor.__class__.__name__}"
                )
                file_context.status = FileStatus.PROCESSING
                try:
                    # Execute current processor
                    processed_items = processor.process(file_context, output_dir)

                    # Recursively process resulting items
                    final_results = []
                    for item in processed_items:
                        if item.status == FileStatus.FAILED:
                            final_results.append(item)
                            continue

                        if (
                            item.local_path == file_context.local_path
                            and item.status == file_context.status
                        ):
                            final_results.append(item)
                        else:
                            next_output_dir = (
                                Path(item.local_path).parent
                                if item.local_path
                                else output_dir
                            )
                            final_results.extend(self.process(item, next_output_dir))

                    return final_results

                except Exception as e:
                    logger.error(
                        f"Error processing file {file_context.source_path}: {str(e)}"
                    )
                    file_context.status = FileStatus.FAILED
                    file_context.error_message = str(e)
                    return [file_context]

        return [file_context]

    def add_processor(self, processor: FileProcessor) -> None:
        """Add a processor to the chain.

        Args:
            processor: Processor to add
        """
        self.processors.append(processor)

    def get_processors(self) -> List[FileProcessor]:
        """Get all processors in the chain.

        Returns:
            List of processors
        """
        return self.processors.copy()
