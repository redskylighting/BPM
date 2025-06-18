# data_scraper.py
import docx
import fitz # PyMuPDF
import os

ALLOWED_EXTENSIONS = {'txt', 'docx', 'pdf'}

def is_allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def scrape_text_from_file(filepath):
    _, extension = os.path.splitext(filepath)
    extension = extension.lower()
    text = ""
    try:
        if extension == '.txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f: text = f.read()
        elif extension == '.docx':
            doc = docx.Document(filepath)
            text = '\n'.join([para.text for para in doc.paragraphs])
        elif extension == '.pdf':
            with fitz.open(filepath) as doc:
                text = "".join(page.get_text() for page in doc)
    except Exception as e:
        print(f"Error scraping file {filepath}: {e}")
        return None
    return text