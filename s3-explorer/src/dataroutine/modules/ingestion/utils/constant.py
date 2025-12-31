WORD_EXTENSIONS = [
    ".docx",
    ".doc",
]

PDF_EXTENSIONS = [
    ".pdf",
]

PPT_EXTENSIONS = [
    ".ppt",
    ".pptx",
    ".pptm",
]

EXCEL_EXTENSIONS = [
    ".xlsx",
    ".xlsm",
    ".xls",
    ".xlsb",
    ".xla",
]

CSV_EXTENSION = ".csv"

MARKITDOWN_IMAGE_EXTENSIONS = [
    ".jpg",
    ".jpeg",
    ".png",
]

OTHER_IMAGE_EXTENSIONS = [
    ".gif",
    ".bmp",
    ".tiff",
    ".webp",
]

IMAGE_EXTENSIONS = [
    *MARKITDOWN_IMAGE_EXTENSIONS,
    *OTHER_IMAGE_EXTENSIONS,
]

TEXT_EXTENSIONS = [
    ".txt",
    ".json",
    ".html",
    CSV_EXTENSION,
]

# List of supported document extensions for extraction
SUPPORTED_DOCUMENT_EXTENSIONS = {
    *WORD_EXTENSIONS,
    *PDF_EXTENSIONS,
    *PPT_EXTENSIONS,
    *EXCEL_EXTENSIONS,
    *IMAGE_EXTENSIONS,
    *TEXT_EXTENSIONS,
}

SUPPORTED_SPREADSHEET_EXTENSIONS = [
    *EXCEL_EXTENSIONS,
    CSV_EXTENSION,
]

# Max workers for extracting text from files
MAX_WORKERS = 4
