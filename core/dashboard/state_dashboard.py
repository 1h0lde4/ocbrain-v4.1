import logging
import json
from core.meta.self_model import SELF_MODEL
from core.meta.introspection import summarize_system_state

logger = logging.getLogger("ocbrain.dashboard")

class StateDashboard:
    """
    Displays and exports the current system state for observability.
    """
    def __init__(self):
        pass

    def get_json_state(self) -> str:
        """Returns the entire SELF_MODEL as a JSON string."""
        return json.dumps(SELF_MODEL, indent=2)

    def print_text_dashboard(self):
        """Prints a human-readable summary of the system state to the logs."""
        summary = summarize_system_state()
        logger.info("\n" + "="*40 + "\n" + "OCBRAIN SYSTEM DASHBOARD\n" + "="*40)
        logger.info(summary)
        
        caps = [k for k, v in SELF_MODEL["capabilities"].items() if v]
        logger.info(f"Active Capabilities: {', '.join(caps)}")
        
        health = SELF_MODEL["health"]
        logger.info(f"Provider Health: {health['provider_reliability']}")
        
        upgrades = SELF_MODEL["pending_upgrades"]
        if upgrades:
            logger.info(f"Pending Upgrades: {len(upgrades)}")
        
        logger.info("="*40 + "\n")

# Global singleton
dashboard = StateDashboard()
