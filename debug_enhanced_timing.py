#!/usr/bin/env python3
"""
Enhanced debugging script that patches the backend to add detailed timing information.
This will help identify exactly where delays occur in the pipeline.
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime
import logging
import sys
import os

# Add backend to path
sys.path.append('/Users/mathewalexander/Documents/projects/live_thought/backend')

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TimingPatcher:
    """Patches backend services to add timing information"""
    
    def __init__(self):
        self.timings = {}
        self.start_time = time.time()
        
    def log_timing(self, event, details=""):
        current_time = time.time()
        elapsed = (current_time - self.start_time) * 1000  # milliseconds
        timestamp = datetime.fromtimestamp(current_time).strftime("%H:%M:%S.%f")[:-3]
        
        timing_info = {
            'timestamp': timestamp,
            'elapsed_ms': round(elapsed, 2),
            'event': event,
            'details': details
        }
        
        self.timings[event] = timing_info
        logger.info(f"⏱️  [{elapsed:>8.2f}ms] {event}: {details}")
        
    def get_summary(self):
        return dict(self.timings)

# Global timing patcher
timing_patcher = TimingPatcher()

async def test_with_enhanced_timing():
    """Test the backend with enhanced timing information"""
    
    query = "What are the current trends in renewable energy technology?"
    run_id = f"enhanced_debug_{int(time.time())}"
    
    timing_patcher.log_timing("TEST_START", f"Query: {query}")
    
    async with aiohttp.ClientSession() as session:
        stream_url = f"http://localhost:8000/v1/stream/{run_id}"
        params = {"query": query}
        
        timing_patcher.log_timing("HTTP_REQUEST_START", stream_url)
        
        try:
            async with session.get(stream_url, params=params) as response:
                timing_patcher.log_timing("HTTP_RESPONSE_RECEIVED", f"Status: {response.status}")
                
                if response.status != 200:
                    logger.error(f"HTTP Error: {response.status}")
                    return
                
                event_count = 0
                first_event_time = None
                last_event_time = None
                
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if not line or line == "data: [DONE]":
                        continue
                        
                    if line.startswith('data: '):
                        event_count += 1
                        current_time = time.time()
                        
                        if first_event_time is None:
                            first_event_time = current_time
                            timing_patcher.log_timing("FIRST_EVENT_RECEIVED", f"Event #{event_count}")
                        
                        last_event_time = current_time
                        
                        data = line[6:]  # Remove 'data: ' prefix
                        
                        try:
                            event = json.loads(data)
                            event_type = event.get('type', 'unknown')
                            content = event.get('content', event.get('data', ''))
                            
                            # Log every 10th event to avoid spam
                            if event_count % 10 == 0 or event_count <= 5:
                                timing_patcher.log_timing(
                                    f"EVENT_{event_count}",
                                    f"Type: {event_type}, Content: {str(content)[:50]}..."
                                )
                                
                        except json.JSONDecodeError:
                            timing_patcher.log_timing(
                                f"RAW_EVENT_{event_count}",
                                f"Raw data: {data[:50]}..."
                            )
                
                timing_patcher.log_timing("STREAM_COMPLETE", f"Total events: {event_count}")
                
                # Calculate streaming statistics
                if first_event_time and last_event_time and event_count > 1:
                    stream_duration = (last_event_time - first_event_time) * 1000  # ms
                    avg_interval = stream_duration / (event_count - 1)
                    timing_patcher.log_timing(
                        "STREAM_STATS",
                        f"Duration: {stream_duration:.2f}ms, Avg interval: {avg_interval:.2f}ms"
                    )
                        
        except Exception as e:
            timing_patcher.log_timing("ERROR", str(e))
            logger.error(f"Stream error: {e}")
    
    # Print detailed summary
    print_timing_analysis()

def print_timing_analysis():
    """Print detailed timing analysis"""
    print("\n" + "="*80)
    print("DETAILED TIMING ANALYSIS")
    print("="*80)
    
    timings = timing_patcher.get_summary()
    
    # Key milestone analysis
    milestones = [
        "TEST_START",
        "HTTP_REQUEST_START", 
        "HTTP_RESPONSE_RECEIVED",
        "FIRST_EVENT_RECEIVED",
        "STREAM_COMPLETE"
    ]
    
    print("\nKey Milestones:")
    prev_time = None
    for milestone in milestones:
        if milestone in timings:
            timing = timings[milestone]
            elapsed = timing['elapsed_ms']
            
            if prev_time is not None:
                gap = elapsed - prev_time
                print(f"  {milestone:>25}: {elapsed:>8.2f}ms (+{gap:>6.2f}ms) - {timing['details']}")
            else:
                print(f"  {milestone:>25}: {elapsed:>8.2f}ms - {timing['details']}")
            
            prev_time = elapsed
    
    # Identify potential bottlenecks
    print("\nBottleneck Analysis:")
    
    if "HTTP_REQUEST_START" in timings and "HTTP_RESPONSE_RECEIVED" in timings:
        request_time = timings["HTTP_RESPONSE_RECEIVED"]["elapsed_ms"] - timings["HTTP_REQUEST_START"]["elapsed_ms"]
        print(f"  Initial HTTP request time: {request_time:.2f}ms")
        
    if "HTTP_RESPONSE_RECEIVED" in timings and "FIRST_EVENT_RECEIVED" in timings:
        processing_time = timings["FIRST_EVENT_RECEIVED"]["elapsed_ms"] - timings["HTTP_RESPONSE_RECEIVED"]["elapsed_ms"]
        print(f"  Time to first event: {processing_time:.2f}ms")
        
        if processing_time > 5000:  # More than 5 seconds
            print(f"    ⚠️  BOTTLENECK: Long delay before first event!")
            print(f"    This suggests backend processing (search/scraping) is slow")
        elif processing_time > 1000:  # More than 1 second
            print(f"    ⚠️  MINOR DELAY: Noticeable delay before first event")
        else:
            print(f"    ✅  GOOD: Quick response to first event")
    
    # Check for streaming consistency
    event_timings = [(k, v) for k, v in timings.items() if k.startswith("EVENT_")]
    if len(event_timings) >= 2:
        event_timings.sort(key=lambda x: x[1]['elapsed_ms'])
        
        intervals = []
        for i in range(1, len(event_timings)):
            interval = event_timings[i][1]['elapsed_ms'] - event_timings[i-1][1]['elapsed_ms']
            intervals.append(interval)
        
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            min_interval = min(intervals)
            max_interval = max(intervals)
            
            print(f"\nEvent Streaming Analysis:")
            print(f"  Average interval between events: {avg_interval:.2f}ms")
            print(f"  Min interval: {min_interval:.2f}ms")
            print(f"  Max interval: {max_interval:.2f}ms")
            
            # Check for batching patterns
            large_gaps = [i for i in intervals if i > avg_interval * 3]
            if large_gaps:
                print(f"  ⚠️  Irregular streaming detected: {len(large_gaps)} large gaps")
                print(f"  Large gaps: {[round(g, 2) for g in large_gaps[:5]]}ms...")
            else:
                print(f"  ✅  Consistent streaming pattern")

async def test_backend_responsiveness():
    """Test how quickly the backend responds to requests"""
    print("🏃‍♂️ Testing Backend Responsiveness...")
    
    # Test simple endpoint first
    timing_patcher.log_timing("HEALTH_CHECK_START", "Testing /health endpoint")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("http://localhost:8000/health") as response:
                timing_patcher.log_timing("HEALTH_CHECK_RESPONSE", f"Status: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    timing_patcher.log_timing("HEALTH_CHECK_COMPLETE", f"Data: {data}")
                else:
                    timing_patcher.log_timing("HEALTH_CHECK_ERROR", f"Failed with status {response.status}")
                    
        except Exception as e:
            timing_patcher.log_timing("HEALTH_CHECK_EXCEPTION", str(e))

if __name__ == "__main__":
    print("🔬 Enhanced Event Timing Debugger")
    print("This will provide detailed timing analysis of the streaming pipeline")
    print("Make sure the backend is running on localhost:8000")
    print("-" * 80)
    
    async def run_all_tests():
        await test_backend_responsiveness()
        print("\n" + "-" * 80)
        await test_with_enhanced_timing()
    
    asyncio.run(run_all_tests())
