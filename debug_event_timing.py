#!/usr/bin/env python3
"""
Debug script to analyze event timing and identify where batching occurs.
This will help determine if the issue is in OpenAI streaming, backend processing, or frontend display.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EventTimingDebugger:
    def __init__(self):
        self.events = []
        self.start_time = None
        
    def log_event(self, event_type, data, source="unknown"):
        current_time = time.time()
        if self.start_time is None:
            self.start_time = current_time
            
        timestamp = datetime.fromtimestamp(current_time).strftime("%H:%M:%S.%f")[:-3]
        elapsed = round((current_time - self.start_time) * 1000, 2)  # milliseconds
        
        event_info = {
            'timestamp': timestamp,
            'elapsed_ms': elapsed,
            'type': event_type,
            'source': source,
            'data': data[:100] if isinstance(data, str) else str(data)[:100]  # Truncate for readability
        }
        
        self.events.append(event_info)
        logger.info(f"[{elapsed:>8.2f}ms] {event_type:>15} | {source:>10} | {data[:50]}...")
        
    def print_summary(self):
        print("\n" + "="*80)
        print("EVENT TIMING SUMMARY")
        print("="*80)
        
        if not self.events:
            print("No events recorded")
            return
            
        # Group events by type
        event_types = {}
        for event in self.events:
            event_type = event['type']
            if event_type not in event_types:
                event_types[event_type] = []
            event_types[event_type].append(event)
            
        for event_type, events in event_types.items():
            print(f"\n{event_type.upper()} Events: {len(events)}")
            if events:
                first_time = events[0]['elapsed_ms']
                last_time = events[-1]['elapsed_ms']
                duration = last_time - first_time
                print(f"  First: {first_time}ms, Last: {last_time}ms, Duration: {duration}ms")
                
                # Check for gaps
                if len(events) > 1:
                    gaps = []
                    for i in range(1, len(events)):
                        gap = events[i]['elapsed_ms'] - events[i-1]['elapsed_ms']
                        gaps.append(gap)
                    avg_gap = sum(gaps) / len(gaps)
                    max_gap = max(gaps)
                    print(f"  Avg gap: {avg_gap:.2f}ms, Max gap: {max_gap:.2f}ms")
                    
                    # Identify potential batching (large gaps)
                    large_gaps = [g for g in gaps if g > 1000]  # Gaps > 1 second
                    if large_gaps:
                        print(f"  ⚠️  Large gaps detected: {large_gaps}")

async def test_backend_streaming():
    """Test the backend streaming endpoint directly"""
    debugger = EventTimingDebugger()
    
    # Start a new query
    query = "What are the latest developments in AI safety research?"
    run_id = f"debug_timing_{int(time.time())}"
    
    debugger.log_event("REQUEST_START", f"Starting query: {query}", "CLIENT")
    
    async with aiohttp.ClientSession() as session:
        # Start the stream
        stream_url = f"http://localhost:8000/v1/stream/{run_id}"
        params = {"query": query}
        
        debugger.log_event("HTTP_REQUEST", f"GET {stream_url}", "CLIENT")
        
        try:
            async with session.get(stream_url, params=params) as response:
                debugger.log_event("HTTP_RESPONSE", f"Status: {response.status}", "BACKEND")
                
                if response.status != 200:
                    logger.error(f"HTTP Error: {response.status}")
                    return
                
                # Read the stream
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if not line:
                        continue
                        
                    if line.startswith('data: '):
                        data = line[6:]  # Remove 'data: ' prefix
                        
                        try:
                            event = json.loads(data)
                            event_type = event.get('type', 'unknown')
                            content = event.get('content', event.get('data', ''))
                            
                            debugger.log_event(event_type.upper(), content, "BACKEND")
                            
                        except json.JSONDecodeError:
                            debugger.log_event("RAW_DATA", data, "BACKEND")
                            
        except Exception as e:
            debugger.log_event("ERROR", str(e), "CLIENT")
            logger.error(f"Stream error: {e}")
    
    debugger.print_summary()
    return debugger.events

async def test_direct_openai_timing():
    """Test OpenAI streaming directly to compare timing"""
    try:
        import openai
        from dotenv import load_dotenv
        import os
        
        load_dotenv()
        client = openai.AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        debugger = EventTimingDebugger()
        
        query = "Explain quantum computing in simple terms"
        debugger.log_event("OPENAI_START", query, "OPENAI")
        
        stream = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": query}],
            stream=True,
            temperature=0.7
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                debugger.log_event("TOKEN", content, "OPENAI")
        
        debugger.log_event("OPENAI_END", "Stream complete", "OPENAI")
        debugger.print_summary()
        
    except ImportError:
        logger.warning("OpenAI library not available for direct testing")
    except Exception as e:
        logger.error(f"OpenAI test error: {e}")

async def compare_backend_vs_openai():
    """Run both tests and compare timing patterns"""
    print("🔍 Testing OpenAI Direct Streaming...")
    await test_direct_openai_timing()
    
    print("\n" + "="*80)
    print("🔍 Testing Backend Streaming...")
    backend_events = await test_backend_streaming()
    
    print("\n" + "="*80)
    print("COMPARISON ANALYSIS")
    print("="*80)
    
    # Analyze backend events for patterns
    if backend_events:
        thought_events = [e for e in backend_events if e['type'] == 'THOUGHT']
        token_events = [e for e in backend_events if e['type'] == 'TOKEN']
        
        print(f"Backend Events Summary:")
        print(f"  Total events: {len(backend_events)}")
        print(f"  Thought events: {len(thought_events)}")
        print(f"  Token events: {len(token_events)}")
        
        if thought_events and token_events:
            first_thought = thought_events[0]['elapsed_ms']
            first_token = token_events[0]['elapsed_ms']
            print(f"  First thought at: {first_thought}ms")
            print(f"  First token at: {first_token}ms")
            print(f"  Delay between first thought and token: {first_token - first_thought}ms")
            
        # Check for clustering (batching)
        if len(backend_events) > 1:
            gaps = []
            for i in range(1, len(backend_events)):
                gap = backend_events[i]['elapsed_ms'] - backend_events[i-1]['elapsed_ms']
                gaps.append(gap)
            
            # Identify clusters (events with small gaps followed by large gaps)
            clusters = []
            current_cluster = [backend_events[0]]
            
            for i, gap in enumerate(gaps):
                if gap < 100:  # Small gap - same cluster
                    current_cluster.append(backend_events[i+1])
                else:  # Large gap - new cluster
                    if len(current_cluster) > 1:
                        clusters.append(current_cluster)
                    current_cluster = [backend_events[i+1]]
            
            if len(current_cluster) > 1:
                clusters.append(current_cluster)
                
            if clusters:
                print(f"\n⚠️  POTENTIAL BATCHING DETECTED:")
                for i, cluster in enumerate(clusters):
                    start_time = cluster[0]['elapsed_ms']
                    end_time = cluster[-1]['elapsed_ms']
                    print(f"  Cluster {i+1}: {len(cluster)} events from {start_time}ms to {end_time}ms")

if __name__ == "__main__":
    print("🚀 Starting Event Timing Debug...")
    print("This will test both OpenAI direct streaming and backend streaming")
    print("Make sure the backend is running on localhost:8000")
    print("-" * 80)
    
    asyncio.run(compare_backend_vs_openai())
