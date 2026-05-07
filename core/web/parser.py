import logging

logger = logging.getLogger("ocbrain.web.parser")

try:
    from bs4 import BeautifulSoup
except ImportError:
    logger.error("BeautifulSoup not installed. Please run: pip install beautifulsoup4")
    BeautifulSoup = None

def parse_html(html_content: str) -> str:
    """
    Extract main content from HTML, removing scripts, styles, and other boilerplate.
    """
    if not BeautifulSoup:
        logger.warning("[Parser] BeautifulSoup not available, returning raw text or empty string.")
        return ""
        
    if not html_content:
        return ""
        
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script_or_style in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        script_or_style.extract()
        
    # Extract text
    text = soup.get_text(separator=' ')
    
    # Collapse multiple spaces and newlines
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = '\n'.join(chunk for chunk in chunks if chunk)
    
    return text
