import json
from agents.orchestrator_agent import process_request

def test_agents():
    queries = [
        {"intent": "KNOWLEDGE", "query": "What is the delay precedent for generator shipments?"},
        {"intent": "PROCUREMENT", "query": "Please analyze vendor tenders.", "context": {"tenders": [{"vendor": "A", "price": 100}, {"vendor": "B", "price": 90}]}},
        {"intent": "QUALITY", "query": "Check compliance for purchase order.", "context": {"po_id": "po-ps1500-001"}},
        {"intent": "SCHEDULE", "query": "Run a schedule risk analysis for the critical path."},
        {"intent": "COMMISSIONING", "query": "Start commissioning tests for the cooling units.", "context": {"task_id": "TASK-123"}},
        {"intent": "REPORT", "query": "Give me a project dashboard report metric."}
    ]

    for q in queries:
        print(f"\\n--- Testing Intent: {q['intent']} ---")
        print(f"Query: {q['query']}")
        try:
            response = process_request(query=q['query'], context=q.get("context", {}))
            print(f"Result Intent: {response.get('intent')}")
            
            # Print truncated response to avoid too much text
            res_str = json.dumps(response.get('agent_response', {}), indent=2)
            if len(res_str) > 500:
                print(f"Response: {res_str[:500]}... [TRUNCATED]")
            else:
                print(f"Response: {res_str}")
        except Exception as e:
            print(f"Error occurred: {e}")

if __name__ == "__main__":
    test_agents()
