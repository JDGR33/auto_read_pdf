from pypdf import PdfReader


def extract_text_from_pdf(pdf_path: str, start_page: int, end_page: int) -> str:
    """Extract raw text from a PDF file for a given 1-based inclusive page range.

    Args:
        pdf_path: Path to the PDF file.
        start_page: Starting page number (1-based, inclusive).
        end_page: Ending page number (1-based, inclusive).

    Returns:
        Combined raw text from the specified page range.
    """
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)

    if start_page < 1 or end_page < start_page or end_page > total_pages:
        raise ValueError(
            f"Invalid page range {start_page}-{end_page}. "
            f"PDF has {total_pages} pages (valid range: 1-{total_pages})."
        )

    pages_text = []
    for page_num in range(start_page, end_page + 1):
        text = reader.pages[page_num - 1].extract_text() or ""
        if text.strip():
            pages_text.append(f"--- [Page {page_num}] ---\n{text}")

    return "\n\n".join(pages_text)
