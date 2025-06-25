import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_query():
    # Start a new query
    response = requests.post(f"{BASE_URL}/v1/query", 
        json={
            "query": "What is the capital of France?",
            "model": "gpt-4"
        }
    )
    print("Query Status Code:", response.status_code)
    data = response.json()
    print("Query Response:", data)
    return data.get("run_id")

def test_stream_events(run_id):
    # Test streaming events
    print(f"\nStreaming events for run_id: {run_id}")
    response = requests.get(f"{BASE_URL}/v1/stream/{run_id}", stream=True)
    
    for line in response.iter_lines():
        if line and line.startswith(b"data: "):
            try:
                data = json.loads(line.decode('utf-8').replace('data: ', ''))
                print(f"\nEvent Type: {data.get('type')}")
                print(f"Content: {data.get('text')}")
                
                # Break if we get a complete or error event
                if data.get('type') in ['complete', 'error']:
                    break
            except json.JSONDecodeError:
                print("Could not decode:", line)

if __name__ == "__main__":
    print("Testing API endpoints...")
    print("1. Creating a new query")
    run_id = test_query()
    
    if run_id:
        print("\n2. Testing event stream")
        test_stream_events(run_id)
    else:
        print("Failed to get run_id, cannot test streaming")
