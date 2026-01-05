import unicodedata
import re
import sys
import threading
import time


class Spinner:
    """A simple terminal loading spinner that displays dots."""
    
    def __init__(self, message="Loading"):
        self.message = message
        self.running = False
        self.thread = None
    
    def _spin(self):
        """Internal method to animate the spinner."""
        dots = 0
        while self.running:
            sys.stdout.write(f"\r{self.message}{'.' * (dots + 1)}   ")
            sys.stdout.flush()
            dots = (dots + 1) % 3
            time.sleep(0.5)
    
    def __enter__(self):
        """Start the spinner."""
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the spinner and clear the line."""
        self.running = False
        if self.thread:
            self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        sys.stdout.flush()
        return False


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