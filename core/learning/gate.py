import logging
from core.learning.similarity import semantic_similarity
from core.learning.evaluator import llm_judge

logger = logging.getLogger("ocbrain.learning.gate")

async def should_learn(chunk: str, answer: str) -> bool:
    """
    Evaluation Gate (CRITICAL).
    Determines if a piece of information extracted from the web is high-quality and 
    relevant enough to be added to long-term memory.
    """
    # 1. Relevance check: is the chunk semantically similar to the target answer/topic?
    sim = semantic_similarity(chunk, answer)
    if sim < 0.6:
        logger.debug(f"[Gate] Rejected: Low similarity ({sim:.2f} < 0.6)")
        return False

    # 2. Quality check: does the LLM judge deem this chunk factual, useful, and high quality?
    evaluation = await llm_judge(chunk)
    score = evaluation.get("score", 0.0)
    reason = evaluation.get("reason", "No reason provided")
    
    if score > 0.7:
        logger.info(f"[Gate] Accepted: Score {score:.2f}. Reason: {reason}")
        return True
    else:
        logger.debug(f"[Gate] Rejected: Low quality score ({score:.2f} <= 0.7). Reason: {reason}")
        return False
