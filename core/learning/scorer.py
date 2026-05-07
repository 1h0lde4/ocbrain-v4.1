def calculate_confidence(similarity_score: float, llm_judge_score: float, source_trust_factor: float = 1.0) -> float:
    """
    Combines the semantic similarity score and the LLM judge score to derive an 
    overall confidence metric for a newly learned fact.
    
    Args:
        similarity_score: Normalized [0-1] score comparing chunk to original context.
        llm_judge_score: Normalized [0-1] score from the LLM evaluator.
        source_trust_factor: Optional multiplier based on domain reputation.
        
    Returns:
        float: Final normalized [0-1] confidence score.
    """
    # A simple weighted average favoring the LLM's nuanced judgment
    base_confidence = (similarity_score * 0.4) + (llm_judge_score * 0.6)
    
    final_confidence = base_confidence * source_trust_factor
    
    # Bound between 0 and 1
    return max(0.0, min(1.0, final_confidence))
