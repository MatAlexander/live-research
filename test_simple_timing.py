#!/usr/bin/env python3
"""
Simple timing test with timeout to avoid hanging and focus on the core issue.
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

async def test_simple_query_timing():
    """Test a simple query with detailed timing and timeout"""
    
    query = "What is 2+2?"  # Simple test query to avoid long search/scraping
    run_id = f"simple_timing_{int(time.time())}"
    
    start_time = time.time()
    events = []
    
    def log_timing(event, details=""):
        elapsed = (time.time() - start_time) * 1000  # milliseconds
        timestamp = datetime.fromtimestamp(time.time()).strftime("%H:%M:%S.%f")[:-3]
        
        events.append({
            'timestamp': timestamp,
            'elapsed_ms': round(elapsed, 2),
            'event': event,
            'details': details
        })
        
        logger.info(f"[{elapsed:>8.2f}ms] {event}: {details}")
    
    log_timing("TEST_START", f"Simple query: {query}")
    
    timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        stream_url = f"http://localhost:8000/v1/stream/{run_id}"
        params = {"query": query}
        
        log_timing("HTTP_REQUEST_START", stream_url)
        
        try:
            async with session.get(stream_url, params=params) as response:
                log_timing("HTTP_RESPONSE_RECEIVED", f"Status: {response.status}")
                
                if response.status != 200:
                    logger.error(f"HTTP Error: {response.status}")
                    text = await response.text()
                    logger.error(f"Response: {text}")
                    return events
                
                event_count = 0
                first_event_time = None
                thought_events = 0
                token_events = 0
                
                # Read with timeout
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if not line:
                        continue
                        
                    if line == "data: [DONE]":
                        log_timing("STREAM_DONE", "Received [DONE] marker")
                        break
                        
                    if line.startswith('data: '):
                        event_count += 1
                        current_time = time.time()
                        
                        if first_event_time is None:
                            first_event_time = current_time
                            log_timing("FIRST_EVENT", f"Event #{event_count}")
                        
                        data = line[6:]  # Remove 'data: ' prefix
                        
                        try:
                            event = json.loads(data)
                            event_type = event.get('type', 'unknown')
                            content = event.get('content', event.get('text', event.get('message', '')))
                            
                            # Count different event types
                            if event_type == 'thought':
                                thought_events += 1
                            elif event_type in ['token', 'final_answer_token']:
                                token_events += 1
                            
                            # Log first few events and key events
                            if event_count <= 10 or event_type in ['thought', 'final_answer', 'complete', 'error']:
                                log_timing(
                                    f"EVENT_{event_count}_{event_type.upper()}",
                                    f"{str(content)[:50]}..."
                                )
                            
                            # Stop on completion or error
                            if event_type in ['complete', 'error']:
                                log_timing("STREAM_COMPLETE", f"Ended with {event_type}")
                                break
                                
                        except json.JSONDecodeError as e:
                            log_timing("JSON_ERROR", f"Failed to parse: {data[:50]}...")
                
                log_timing("PROCESSING_COMPLETE", f"Total: {event_count} events, {thought_events} thoughts, {token_events} tokens")
                
        except asyncio.TimeoutError:
            log_timing("TIMEOUT", "Request timed out after 30 seconds")
        except Exception as e:
            log_timing("ERROR", str(e))
            logger.error(f"Stream error: {e}")
    
    # Analyze timing patterns
    print("\n" + "="*80)
    print("TIMING ANALYSIS")
    print("="*80)
    
    if len(events) >= 2:
        # Find key events
        key_events = {}
        for event in events:
            if event['event'] in ['TEST_START', 'HTTP_REQUEST_START', 'HTTP_RESPONSE_RECEIVED', 
                                'FIRST_EVENT', 'STREAM_COMPLETE', 'PROCESSING_COMPLETE']:
                key_events[event['event']] = event
        
        print("\nKey Milestones:")
        for event_name in ['TEST_START', 'HTTP_REQUEST_START', 'HTTP_RESPONSE_RECEIVED', 
                          'FIRST_EVENT', 'STREAM_COMPLETE', 'PROCESSING_COMPLETE']:
            if event_name in key_events:
                event = key_events[event_name]
                print(f"  {event_name:>20}: {event['elapsed_ms']:>8.2f}ms - {event['details']}")
        
        # Calculate delays
        if 'HTTP_REQUEST_START' in key_events and 'HTTP_RESPONSE_RECEIVED' in key_events:
            delay = key_events['HTTP_RESPONSE_RECEIVED']['elapsed_ms'] - key_events['HTTP_REQUEST_START']['elapsed_ms']
            print(f"\n🔍 HTTP Response Delay: {delay:.2f}ms")
        
        if 'HTTP_RESPONSE_RECEIVED' in key_events and 'FIRST_EVENT' in key_events:
            delay = key_events['FIRST_EVENT']['elapsed_ms'] - key_events['HTTP_RESPONSE_RECEIVED']['elapsed_ms']
            print(f"🔍 Time to First Event: {delay:.2f}ms")
            
            if delay > 5000:
                print("   ⚠️  MAJOR BOTTLENECK: >5 seconds before first event!")
                print("   This suggests backend processing (search/scraping) is blocking")
            elif delay > 1000:
                print("   ⚠️  MINOR DELAY: >1 second before first event")
            else:
                print("   ✅  GOOD: Quick response")
        
        # Check for event clustering (batching)
        event_timings = [e for e in events if e['event'].startswith('EVENT_')]
        if len(event_timings) >= 2:
            gaps = []
            for i in range(1, len(event_timings)):
                gap = event_timings[i]['elapsed_ms'] - event_timings[i-1]['elapsed_ms']
                gaps.append(gap)
            
            if gaps:
                avg_gap = sum(gaps) / len(gaps)
                max_gap = max(gaps)
                min_gap = min(gaps)
                
                print(f"\n🔍 Event Streaming Pattern:")
                print(f"   Average gap: {avg_gap:.2f}ms")
                print(f"   Min gap: {min_gap:.2f}ms") 
                print(f"   Max gap: {max_gap:.2f}ms")
                
                # Look for batching (big gaps followed by small gaps)
                large_gaps = [g for g in gaps if g > 1000]
                if large_gaps:
                    print(f"   ⚠️  BATCHING DETECTED: {len(large_gaps)} gaps >1000ms")
                    print(f"   Large gaps: {large_gaps[:3]}...")
                else:
                    print(f"   ✅  NO BATCHING: All gaps <1000ms")
    
    return events

if __name__ == "__main__":
    print("🕐 Simple Timing Test with Timeout")
    print("Testing simple query to identify where delays occur")
    print("-" * 80)
    
    asyncio.run(test_simple_query_timing())
