# A simple utility for PDF extraction, a common task in such projects
# Requires: pip install pypdf

from pypdf import PdfReader

def extract_text_from_pdf(filepath: str) -> str:
    """Extracts text from all pages of a PDF and returns it as a single string."""
    print(f"-> Processor: Extracting text from PDF: {filepath}")
    text = ""
    try:
        reader = PdfReader(filepath)
        for page in reader.pages:
            text += page.extract_text() + "\n---\n" # Separator for page breaks
        return text
    except Exception as e:
        return f"ERROR: Could not process PDF at {filepath}. Reason: {e}"