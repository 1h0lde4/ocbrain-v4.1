import logging

logger = logging.getLogger("ocbrain.learning.similarity")

# Global reference for lazy loading
_model = None

def get_model():
    """
    Lazy loads the embedding model to prevent large overhead 
    on initial module import.
    """
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Suppress noisy logs from sentence-transformers if needed
            logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
            logger.info("Loading SentenceTransformer model...")
            _model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Model loaded successfully.")
        except ImportError:
            logger.error("sentence-transformers is not installed. Similarity scores will be 0.0.")
            return None
    return _model

def semantic_similarity(a: str, b: str) -> float:
    """
    Computes cosine similarity between two strings using a local embedding model.
    Returns a normalized score [0-1].
    """
    if not a or not b:
        return 0.0
        
    model = get_model()
    if not model:
        return 0.0

    try:
        from scipy.spatial.distance import cosine
    except ImportError:
        logger.error("scipy is not installed. Similarity scores will be 0.0.")
        return 0.0

    embeddings = model.encode([a, b])
    # cosine() returns distance [0, 2]. Similarity is 1 - distance.
    # To strictly normalize to [0, 1], we bound it.
    dist = cosine(embeddings[0], embeddings[1])
    sim = max(0.0, min(1.0, 1.0 - dist))
    return float(sim)
