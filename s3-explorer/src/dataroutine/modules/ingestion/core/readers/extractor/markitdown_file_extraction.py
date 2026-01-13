import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, List

import dspy
import pymupdf
from markitdown import MarkItDown
from PIL import Image
from dataroutine.modules.ingestion.core.mock_model import MockOpenAIClient
from dataroutine.modules.ingestion.env import (
    LLM_API_BASE_URL,
    LLM_API_KEY,
    LLM_API_VERSION,
    LLM_MAX_TOKEN,
    LLM_MODEL_ID,
    LLM_PROVIDER,
)
from dataroutine.modules.ingestion.utils.constant import (
    MAX_WORKERS,
    PDF_EXTENSIONS,
    SUPPORTED_DOCUMENT_EXTENSIONS,
)
from dataroutine.modules.ingestion.utils.file_helper import FileHelper
from dataroutine.modules.ingestion.utils.llm_helper import LLMHelper
from dataroutine.shared._logging import get_logger
from markitdown.converters import *
from .audio_converter import AudioLLMConverter
logger = get_logger(__name__)

FILE_EXTRACTION = """
## Instruction
You are an intelligent OCR tool.
Your task: **Accurately extract all content from the image** into text.

### Requirements
- Preserve the **original language** (do not translate or convert).
- Preserve the **text formatting**:
  - Line breaks
  - Whitespace
  - Punctuation
  - Bullet/Number lists
  - Tables (use Markdown table format if possible)
  - Special characters
- Do not add, omit, or speculate on content.
- If any part is unreadable, mark it as `[unclear]`.

### Output
- Return the **extracted content in Markdown format**.
- Do not add any explanations or descriptions outside of the text.
"""


class MarkitdownFileExtractor:
    """
    A comprehensive file extraction utility for processing various document formats.

    This class provides methods to extract text content from:
    - PDF files (using sliding window approach for large documents)
    - Image files (PNG, JPG, JPEG, etc.)
    - Office documents (Word, Excel, PowerPoint, etc.)

    The extracted content is returned as DocumentSchema objects with appropriate metadata.
    """

    def __init__(self, model: Any = None):
        self.model = model

    def _combine_page_images(
        self, doc, page_numbers: list[int], dpi: int = 144
    ) -> io.BytesIO:
        """
        Combine multiple PDF pages into a single image.
        Args:
            doc: PyMuPDF document object
            page_numbers: List of page numbers to combine
            dpi: DPI for image conversion
        Returns:
            io.BytesIO: Combined image as BytesIO stream
        """
        images = []
        max_width = 0
        max_height = 0

        # Convert each page to image and collect dimensions
        for page_num in page_numbers:
            if page_num < len(doc):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=dpi)
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))
                images.append(img)
                max_width += img.width
                max_height = max(max_height, img.height)

        if not images:
            # Return empty stream if no valid pages
            return io.BytesIO()

        # Create combined image (horizontal stacking)
        combined_image = Image.new("RGB", (max_width, max_height), "white")
        x_offset = 0

        for img in images:
            combined_image.paste(img, (x_offset, 0))
            x_offset += img.width

        # Convert combined image to BytesIO
        img_stream = io.BytesIO()
        combined_image.save(img_stream, format="PNG")
        img_stream.seek(0)

        return img_stream

    def _choose_markitdown_model(self) -> tuple[MarkItDown, str]:
        """Choose the appropriate MarkItDown model and prompt based on availability."""

        formatted_model_name = LLMHelper.format_model_id_name(
            LLM_MODEL_ID, LLM_PROVIDER
        )

        if self.model:
            llm_model = self.model
            # Use model's internal name if available, otherwise default to env-based name
            model_name = getattr(self.model, "model", formatted_model_name)
        else:
            try:
                llm_model = dspy.LM(
                    model=formatted_model_name,
                    api_key=LLM_API_KEY or None,
                    api_base=LLM_API_BASE_URL or None,
                    api_version=LLM_API_VERSION or None,
                    max_tokens=LLM_MAX_TOKEN,
                    cache=False,
                )
            except Exception as model_error:
                logger.error(
                    "Failed to initialize MarkItDown LLM client for model %s: %s",
                    formatted_model_name,
                    model_error,
                )
                raise
            model_name = formatted_model_name

        prompt = FILE_EXTRACTION

        # Create MarkItDown instance with configured model
        mock_client = MockOpenAIClient(model=llm_model)
        _markitdown = MarkItDown(llm_client=mock_client, llm_model=model_name, enable_builtins=True)

        _markitdown.register_converter(DocxConverter())
        _markitdown.register_converter(XlsxConverter())
        _markitdown.register_converter(XlsConverter())
        _markitdown.register_converter(PptxConverter())
        _markitdown.register_converter(AudioLLMConverter())
        _markitdown.register_converter(ImageConverter())
        _markitdown.register_converter(IpynbConverter())
        _markitdown.register_converter(PdfConverter())
        _markitdown.register_converter(OutlookMsgConverter())
        _markitdown.register_converter(EpubConverter())
        _markitdown.register_converter(CsvConverter())
        

        return _markitdown, prompt

    def read_pages(self, file_path: str, max_pages: int = 3) -> str:
        """Extract text from the first N pages of a PDF file.

        Args:
            file_path: Path to the PDF file
            max_pages: Maximum number of pages to read (default: 3)

        Returns:
            Extracted text content
        """
        if FileHelper.get_file_size(file_path) == 0:
            logger.error(f"File size of ({file_path}) is 0, skipping extraction...")
            return ""

        md, prompt = self._choose_markitdown_model()
        return self._extract_pdf_pages(file_path, max_pages, md, prompt)

    def _extract_pdf_pages(
        self, file_path: str, max_pages: int, md: MarkItDown, prompt: str
    ) -> str:
        """Extract content from the first N pages of a PDF.

        Args:
            file_path: Path to the PDF file
            max_pages: Maximum number of pages to extract
            md: MarkItDown instance
            prompt: Prompt for extraction

        Returns:
            Extracted text content
        """
        doc = pymupdf.open(file_path)
        try:
            total_pages = min(len(doc), max_pages)

            if total_pages == 0:
                return ""

            page_numbers = list(range(total_pages))
            combined_image_stream = self._combine_page_images(doc, page_numbers)

            content = ""
            if combined_image_stream.getvalue():
                result = md.convert_stream(
                    combined_image_stream,
                    file_extension="png",
                    llm_prompt=prompt,
                )
                content = result.text_content

            return content
        finally:
            doc.close()

    def _extract_with_markitdown(
        self, file_path: str, md: MarkItDown, prompt: str
    ) -> str:
        """Extract content from a file using MarkItDown directly.

        Args:
            file_path: Path to the file
            md: MarkItDown instance
            prompt: Prompt for extraction

        Returns:
            Extracted text content
        """
        try:
            result = md.convert(file_path, llm_prompt=prompt)
            return result.text_content
        except Exception as e:
            logger.error(f"Error extracting content from {file_path}: {e}")
            return ""

    def extract_content_from_file(
        self, file_path: str, window_size: int = 3, overlap: int = 1
    ) -> str:
        """
        Extract text content from a supported document file and return as a string.

        Args:
            file_path (str): Path to the document file.
            window_size (int): Number of pages to process together in sliding window (default: 3)
            overlap (int): Number of pages to overlap between consecutive windows (default: 1)
        Returns:
            str: Extracted text content from the document.
        Raises:
            ValueError: If the file extension is not supported or conversion fails, or if window/overlap parameters are invalid.
        """
        logger.info(f"Extracting content from {file_path}")

        # Validate window_size and overlap parameters
        if window_size < 1:
            raise ValueError("window_size must be at least 1")
        if overlap < 0:
            raise ValueError("overlap must be non-negative")
        if overlap >= window_size:
            raise ValueError("overlap must be less than window_size")

        file_extension = FileHelper.get_file_extension(file_path)
        if file_extension not in SUPPORTED_DOCUMENT_EXTENSIONS:
            logger.error(
                f"File extension '{file_extension}' is not supported, skipping extraction..."
            )
            return ""

        # Check file size before processing to avoid the weird markitdown error
        if FileHelper.get_file_size(file_path) == 0:
            logger.error(f"File size of ({file_path}) is 0, skipping extraction...")
            return ""

        # Initialize MarkItDown instance once for the entire extraction process
        md, prompt = self._choose_markitdown_model()

        # Extract based on file type
        if file_extension in PDF_EXTENSIONS:
            return self._extract_pdf_content(
                file_path, window_size, overlap, md, prompt
            )
        else:
            return self._extract_with_markitdown(file_path, md, prompt)

    def _extract_pdf_content(
        self,
        file_path: str,
        window_size: int,
        overlap: int,
        md: MarkItDown,
        prompt: str,
    ) -> str:
        """Extract content from PDF files using sliding window approach.

        Args:
            file_path (str): Path to the PDF file
            window_size (int): Number of pages per window
            overlap (int): Number of pages to overlap between windows

        Returns:
            str: Extracted text content from the PDF file.
        """
        doc = pymupdf.open(file_path)
        try:
            total_pages = len(doc)

            def process_page_window(window_start: int, page_numbers: list[int]):
                """Process a window of PDF pages and return content with window identifier for ordering"""
                logger.info(
                    f"Processing window at pages: {[p + 1 for p in page_numbers]}"
                )

                try:
                    # Combine pages in the window into a single image
                    combined_image_stream = self._combine_page_images(doc, page_numbers)
                    if combined_image_stream.getvalue():
                        # Process the combined image with the shared MarkItDown instance
                        document_content = md.convert_stream(
                            combined_image_stream,
                            file_extension="png",
                            llm_prompt=prompt,
                        )

                        logger.info(
                            f"Page [{page_numbers}] content:\n{document_content.text_content}"
                        )
                        return window_start, document_content.text_content
                    else:
                        return window_start, ""

                except Exception as e:
                    logger.error(
                        f"Error processing window starting at page {window_start + 1}: {e}"
                    )
                    return window_start, ""

            # Create sliding windows with configurable overlap
            windows = self._create_sliding_windows(total_pages, window_size, overlap)

            # Process windows in parallel
            window_contents = {}
            with ThreadPoolExecutor(
                max_workers=min(MAX_WORKERS, len(windows))
            ) as executor:
                # Submit all windows for processing
                future_to_window = {
                    executor.submit(
                        process_page_window, window_start, page_numbers
                    ): window_start
                    for window_start, page_numbers in windows
                }

                # Collect results as they complete
                for future in as_completed(future_to_window):
                    try:
                        window_start, content = future.result()
                        window_contents[window_start] = content
                    except Exception as exc:
                        window_start = future_to_window[future]
                        logger.error(
                            f"Window starting at page {window_start + 1} generated an exception: {exc}"
                        )
                        window_contents[
                            window_start
                        ] = ""  # Use empty content for failed windows

            full_content = ""
            for window_start, _ in sorted(windows):
                window_content = window_contents.get(window_start, "")
                if window_content:
                    full_content += window_content

            return full_content
        finally:
            doc.close()

    def _create_sliding_windows(
        self, total_pages: int, window_size: int, overlap: int
    ) -> List[tuple[int, List[int]]]:
        """Create sliding windows for PDF page processing.

        Args:
            total_pages (int): Total number of pages in the document
            window_size (int): Number of pages per window
            overlap (int): Number of pages to overlap between windows

        Returns:
            List[tuple[int, List[int]]]: List of (window_start, page_numbers) tuples
        """
        windows = []
        step_size = window_size - overlap

        if total_pages <= window_size:
            # If total pages is less than or equal to window size, process all pages in one window
            window_pages = list(range(0, total_pages))
            windows.append((0, window_pages))
        else:
            # Create windows with specified overlap
            i = 0
            while i < total_pages:
                window_end = min(i + window_size, total_pages)
                window_pages = list(range(i, window_end))
                windows.append((i, window_pages))

                # If this window reaches the end, break
                if window_end == total_pages:
                    break

                # Move to next window position
                i += step_size

                # If the next window would be too small or beyond total pages,
                # create a final window that ends at total_pages
                if i + window_size > total_pages and i < total_pages:
                    final_start = max(i, total_pages - window_size)
                    if final_start not in [
                        start for start, _ in windows
                    ]:  # Avoid duplicate windows
                        window_pages = list(range(final_start, total_pages))
                        windows.append((final_start, window_pages))
                    break

        return windows
