import json
import os
import logging

logger = logging.getLogger("ocbrain.shadow.collector")

class ShadowCollector:
    """
    Logs parallel executions of the system's internal reasoning against
    web-derived reasoning, building a dataset for future fine-tuning.
    """
    def __init__(self, log_dir: str = ".data/shadow"):
        self.log_dir = log_dir
        self._ensure_dir()
        self.log_file = os.path.join(self.log_dir, "shadow_log.jsonl")

    def _ensure_dir(self):
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)

    def log_comparison(self, query: str, system_answer: str, web_answer: str, similarity_score: float, confidence: float):
        """
        Stores the comparison between the standard system response and the web-enhanced response.
        """
        entry = {
            "query": query,
            "system_answer": system_answer,
            "web_answer": web_answer,
            "similarity_score": similarity_score,
            "confidence": confidence
        }
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"[ShadowCollector] Failed to write shadow log: {e}")

    def export_training_dataset(self, output_path: str = ".data/shadow/training_dataset.jsonl", min_confidence: float = 0.8):
        """
        Generates a training-ready JSONL dataset from the shadow logs,
        filtering out low-confidence responses.
        
        Format: {"input": "...", "output": "...", "confidence": ...}
        """
        if not os.path.exists(self.log_file):
            logger.warning("[ShadowCollector] No shadow logs available for export.")
            return

        exported_count = 0
        try:
            out_dir = os.path.dirname(output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
                
            with open(self.log_file, "r", encoding="utf-8") as infile, \
                 open(output_path, "w", encoding="utf-8") as outfile:
                 
                for line in infile:
                    if not line.strip():
                        continue
                        
                    data = json.loads(line)
                    if data.get("confidence", 0.0) >= min_confidence:
                        # Map to expected dataset format
                        training_entry = {
                            "input": data["query"],
                            # We assume the web answer is the higher quality 'ground truth' 
                            # if it passed the high confidence threshold
                            "output": data["web_answer"], 
                            "confidence": data["confidence"]
                        }
                        outfile.write(json.dumps(training_entry) + "\n")
                        exported_count += 1
                        
            logger.info(f"[ShadowCollector] Successfully exported {exported_count} high-confidence examples to {output_path}")
        except Exception as e:
            logger.error(f"[ShadowCollector] Failed to export training dataset: {e}")
