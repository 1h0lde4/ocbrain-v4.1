import logging
from typing import List, Dict, Any
from .self_model import SELF_MODEL

logger = logging.getLogger("ocbrain.meta.planner")

class UpgradePlanner:
    """
    Analyzes system weaknesses and proposes intelligent upgrades.
    """
    def __init__(self):
        pass

    def analyze_weaknesses(self) -> List[str]:
        """Identifies areas with low health scores or high failure rates."""
        health = SELF_MODEL["health"]
        weaknesses = []
        
        if health["system_stability"] < 0.8:
            weaknesses.append("system_stability")
            
        for p, score in health["provider_reliability"].items():
            if score < 0.6:
                weaknesses.append(f"provider_reliability:{p}")
                
        if health["retrieval_precision"] < 0.7:
            weaknesses.append("retrieval_precision")
            
        return weaknesses

    def propose_upgrades(self) -> List[Dict[str, Any]]:
        """Generates structured upgrade proposals based on weaknesses."""
        weaknesses = self.analyze_weaknesses()
        proposals = []
        
        for w in weaknesses:
            if w == "retrieval_precision":
                proposals.append({
                    "id": "UPG_MEM_01",
                    "type": "memory_optimization",
                    "benefit": 0.3,
                    "risk": 0.1,
                    "description": "Tune hybrid retrieval weights and perform memory deduplication to improve precision.",
                    "affected_modules": ["memory", "orchestrator"]
                })
            
            if "provider_reliability" in w:
                p_name = w.split(":")[1]
                proposals.append({
                    "id": f"UPG_PROV_{p_name}",
                    "type": "provider_mesh_tuning",
                    "benefit": 0.5,
                    "risk": 0.05,
                    "description": f"Increase retry limit and cooldown period for unstable provider {p_name}.",
                    "affected_modules": ["provider_mesh"]
                })
        
        return proposals

    def prioritize_upgrades(self, proposals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sorts proposals by benefit/risk ratio."""
        return sorted(proposals, key=lambda x: x["benefit"] / max(0.01, x["risk"]), reverse=True)

# Global singleton
upgrade_planner = UpgradePlanner()
