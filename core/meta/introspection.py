import logging
from .self_model import SELF_MODEL

logger = logging.getLogger("ocbrain.meta.introspection")

def explain_capabilities() -> str:
    """
    Returns a factual summary of what the system can currently do.
    """
    caps = [k for k, v in SELF_MODEL["capabilities"].items() if v]
    if not caps:
        return "I currently have no active advanced capabilities."
    
    summary = "My active capabilities include: " + ", ".join(caps).replace("_", " ") + "."
    return summary

def explain_limitations() -> str:
    """
    Returns a factual summary of what the system CANNOT do or what limits it.
    """
    limits = SELF_MODEL["limits"]
    missing = [k for k, v in SELF_MODEL["capabilities"].items() if not v]
    
    explanation = f"My context window is limited to {limits['max_context_length']} tokens. "
    if not limits["vision_enabled"]:
        explanation += "I do not have vision capabilities. "
    
    if missing:
        explanation += "Currently disabled or unavailable features: " + ", ".join(missing).replace("_", " ") + "."
    
    return explanation

def explain_failure(reason: str) -> str:
    """
    Explains a specific failure based on system health and state.
    """
    health = SELF_MODEL["health"]
    if health["system_stability"] < 0.5:
        return f"The request failed due to high system instability ({health['system_stability']})."
    
    low_reliability = [p for p, score in health["provider_reliability"].items() if score < 0.4]
    if low_reliability:
        return f"Generation failed because reliable providers ({', '.join(low_reliability)}) are currently offline or unstable."
    
    return f"Execution failed for the following reason: {reason}"

def summarize_system_state() -> str:
    """
    Provides a high-level overview of the entire OCBrain health and identity.
    """
    id_info = SELF_MODEL["identity"]
    health = SELF_MODEL["health"]
    
    summary = (
        f"I am {id_info['name']} v{id_info['version']} (Phase {id_info['current_phase']}).\n"
        f"System Stability: {health['system_stability']*100}%.\n"
        f"Memory Integrity: {health['memory_integrity']*100}%.\n"
        f"Test Success Rate: {health['test_success_rate']*100}%."
    )
    return summary
