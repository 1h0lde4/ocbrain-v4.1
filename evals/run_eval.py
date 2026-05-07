import json
import asyncio
import os
import sys

# Ensure paths are correct when running from root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.runtime.limits import safe_llm_call
from core.learning.similarity import semantic_similarity

async def mock_ocbrain_call(query: str) -> str:
    """
    Placeholder for actual OCBrain invocation.
    In a real scenario, this would route through the orchestrator.
    """
    # Simple mock that just repeats expected answers for demonstration
    # You should replace this with the actual system call
    await asyncio.sleep(0.1) # Simulate network/processing delay
    return f"Mock answer for: {query}"

async def run_evaluation():
    dataset_path = os.path.join(os.path.dirname(__file__), 'dataset.json')
    with open(dataset_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    print(f"Loaded {len(dataset)} queries. Running evaluation...")
    
    scores = []
    failed_queries = []
    
    for item in dataset:
        query = item["query"]
        expected = item["expected"]
        
        try:
            # We wrap the call in safe_llm_call to enforce limits and timeouts
            actual_answer = await safe_llm_call(mock_ocbrain_call, query)
        except Exception as e:
            actual_answer = ""
            print(f"Error processing query '{query}': {e}")
            
        score = semantic_similarity(expected, actual_answer)
        scores.append(score)
        
        if score < 0.6:
            failed_queries.append({
                "query": query,
                "expected": expected,
                "actual": actual_answer,
                "score": score
            })
            
    if not scores:
        print("No queries evaluated.")
        return
        
    avg_score = sum(scores) / len(scores)
    min_score = min(scores)
    max_score = max(scores)
    
    print("\n--- Evaluation Results ---")
    print(f"Total Evaluated: {len(scores)}")
    print(f"Average Score:   {avg_score:.4f}")
    print(f"Min Score:       {min_score:.4f}")
    print(f"Max Score:       {max_score:.4f}")
    print(f"Failed Queries (< 0.6): {len(failed_queries)}")
    
    if failed_queries:
        print("\n--- Failed Queries Sample ---")
        for fq in failed_queries[:5]:
            print(f"Q: {fq['query']}\nExp: {fq['expected']}\nAct: {fq['actual']}\nScore: {fq['score']:.4f}\n")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
