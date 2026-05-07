import logging
from typing import Dict

logger = logging.getLogger("ocbrain.web_learning.trust")

# Initial list of high-trust domains
TRUSTED_DOMAINS = {
    "wikipedia.org": 0.9,
    "github.com": 0.85,
    "arxiv.org": 0.95,
    "python.org": 1.0,
    "stackoverflow.com": 0.75
}

class TrustManager:
    """
    Scores external sources based on reputation and historical reliability.
    """
    def __init__(self):
        self.source_history: Dict[str, Dict[str, Any]] = {}

    def get_trust_score(self, url: str) -> float:
        """
        Calculates a trust score [0.0 - 1.0] for a given URL.
        """
        domain = self._extract_domain(url)
        base_score = TRUSTED_DOMAINS.get(domain, 0.5) # Default to 0.5 for unknown
        
        # Adjust based on history if available
        if domain in self.source_history:
            stats = self.source_history[domain]
            reliability = stats["validated_count"] / max(1, stats["total_count"])
            base_score = (base_score * 0.7) + (reliability * 0.3)
            
        return round(base_score, 2)

    def record_validation_result(self, url: str, success: bool):
        """Updates source history based on knowledge validation."""
        domain = self._extract_domain(url)
        if domain not in self.source_history:
            self.source_history[domain] = {"total_count": 0, "validated_count": 0}
        
        self.source_history[domain]["total_count"] += 1
        if success:
            self.source_history[domain]["validated_count"] += 1

    def _extract_domain(self, url: str) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.replace("www.", "")
        except:
            return url

# Global singleton
trust_manager = TrustManager()
