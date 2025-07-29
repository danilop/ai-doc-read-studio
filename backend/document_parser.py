import os
import docx
import PyPDF2

def parse_document(file_path: str) -> str:
    """Parse different document types and return text content."""
    _, extension = os.path.splitext(file_path)
    extension = extension.lower()

    try:
        if extension == '.txt':
            return parse_txt(file_path)
        elif extension == '.md':
            return parse_markdown(file_path)
        elif extension == '.docx':
            return parse_docx(file_path)
        elif extension == '.pdf':
            return parse_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {extension}")
    except Exception as e:
        raise Exception(f"Error parsing document: {str(e)}")

def parse_txt(file_path: str) -> str:
    """Parse plain text file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def parse_markdown(file_path: str) -> str:
    """Parse markdown file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
        # For now, just return the raw markdown
        return content

def parse_docx(file_path: str) -> str:
    """Parse Word document."""
    doc = docx.Document(file_path)
    text_content = []

    for paragraph in doc.paragraphs:
        text_content.append(paragraph.text)

    return '\n'.join(text_content)

def parse_pdf(file_path: str) -> str:
    """Parse PDF document."""
    text_content = []

    with open(file_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)

        for page in pdf_reader.pages:
            text_content.append(page.extract_text())

    return '\n'.join(text_content)
