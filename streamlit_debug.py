import requests
import json
import time

def test_streamlit_parsing():
    """Test the Streamlit app's parsing logic"""
    
    # Create a query
    payload = {"query": "What is 2+2?", "model": "o4-mini"}
    response = requests.post("http://localhost:8000/v1/query", json=payload, timeout=10)
    
    if response.status_code == 200:
        result = response.json()
        run_id = result['run_id']
        print(f"Query created with run_id: {run_id}")
        
        # Test the streaming with the same logic as Streamlit
        url = f"http://localhost:8000/v1/stream/{run_id}"
        response = requests.get(url, stream=True, timeout=120)  # Increased timeout
        
        if response.status_code != 200:
            print(f"Stream failed with status {response.status_code}")
            return
        
        buffer = ""
        event_count = 0
        start_time = time.time()
        last_event_time = start_time
        
        print("=== STREAMLIT-STYLE PARSING TEST ===")
        
        for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
            if chunk:
                buffer += chunk
                current_time = time.time()
                print(f"CHUNK at {current_time - start_time:.2f}s: {repr(chunk)}")
                print(f"BUFFER: {repr(buffer)}")
                
                # Process complete lines (same logic as Streamlit)
                while '\n\n' in buffer:
                    line, buffer = buffer.split('\n\n', 1)
                    print(f"LINE: {repr(line)}")
                    
                    if line.startswith('data: '):
                        try:
                            event_data = json.loads(line[6:])  # Remove 'data: ' prefix
                            event_count += 1
                            last_event_time = current_time
                            print(f"✅ EVENT {event_count} at {current_time - start_time:.2f}s: {event_data['type']} - {event_data.get('text', '')[:50]}")
                            
                            if event_data.get('type') == 'final_answer':
                                print(f"🎯 FINAL ANSWER FOUND: {event_data.get('text', '')}")
                            
                            if event_data.get('type') == 'complete':
                                print("✅ STREAM COMPLETE")
                                return
                                
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON decode error: {e}, line: {line}")
                        except Exception as e:
                            print(f"❌ Error processing event: {e}")
            
            # Check if we've been waiting too long
            if time.time() - last_event_time > 30:  # 30 second timeout
                print(f"⚠️ No events received for 30 seconds, stopping")
                break
        
        print(f"🔚 Stream ended after {time.time() - start_time:.2f}s with {event_count} events")
    else:
        print(f"Query failed with status {response.status_code}")

if __name__ == "__main__":
    test_streamlit_parsing() 