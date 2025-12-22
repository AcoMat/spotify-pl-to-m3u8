import unicodedata
import re

def _normalize_text(text):
    """Normalize text by stripping whitespace, removing accents, and normalizing punctuation."""
    if text is None:
        return None
    if isinstance(text, str):
        # Strip whitespace
        text = text.strip()
        if not text:
            return None
        
        # Normalize unicode to NFD form and remove accents
        text = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
        
        # Remove or normalize punctuation: remove commas, periods, hyphens surrounded by spaces
        text = re.sub(r'\s*[,\.]\s*', ' ', text)  # Remove commas and periods with surrounding spaces
        text = re.sub(r'\s+', ' ', text)  # Normalize multiple spaces to single space
        
        # Convert to lowercase for case-insensitive matching
        text = text.lower().strip()
        
        return text if text else None
    return text