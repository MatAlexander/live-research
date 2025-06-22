import os
import asyncio
import json
import uuid
import time
import logging
import sys
from typing import List, Dict, Any, Optional, AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
import uvicorn
from dotenv import load_dotenv

from services.search_service import SearchService
from services.scraper_service import ScraperService
from services.embedding_service import EmbeddingService
from services.agent_service import AgentService
from models.schemas import QueryRequest, ThoughtEvent, TokenEvent
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global services
search_service: Optional[SearchService] = None
scraper_service: Optional[ScraperService] = None
embedding_service: Optional[EmbeddingService] = None
agent_service: Optional[AgentService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application services"""
    global search_service, scraper_service, embedding_service, agent_service
    
    # Initialize services
    search_service = SearchService()
    scraper_service = ScraperService()
    embedding_service = EmbeddingService()
    agent_service = AgentService(search_service, scraper_service, embedding_service)
    
    logger.info("Services initialized successfully")
    yield
    
    # Cleanup
    if scraper_service:
        await scraper_service.cleanup()
    logger.info("Services cleaned up")

app = FastAPI(
    title="AI Thinking Agent API",
    description="Real-time AI agent with visible thinking process",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": time.time()}

@app.get("/test-agent/{run_id}")
async def test_agent(run_id: str):
    """Test agent processing without search/scraping"""
    service = get_agent_service()
    
    # Start a simple test query that goes directly to OpenAI
    asyncio.create_task(service.process_query(run_id, "What is 2+2?", "o4-mini"))
    
    return {"run_id": run_id, "message": "Test agent started"}

@app.get("/test-stream/{run_id}")
async def test_stream(run_id: str):
    """Test streaming endpoint"""
    async def test_generator():
        # Test thought events
        for i in range(3):
            event = {
                "type": "thought",
                "text": f"🧠 Test thought {i+1}: Analyzing information...",
                "timestamp": time.time(),
                "run_id": run_id
            }
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(1)
        
        # Test final answer
        final_event = {
            "type": "final_answer",
            "text": "🎯 This is a test final answer to verify that the streaming and parsing is working correctly!",
            "timestamp": time.time(),
            "run_id": run_id
        }
        yield f"data: {json.dumps(final_event)}\n\n"
        await asyncio.sleep(1)
        
        # Send complete event
        complete_event = {
            "type": "complete",
            "text": "Test complete",
            "timestamp": time.time(),
            "run_id": run_id
        }
        yield f"data: {json.dumps(complete_event)}\n\n"
    
    return StreamingResponse(
        test_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

class LogRequest(BaseModel):
    message: str

@app.post("/log")
async def log_message(request: LogRequest):
    """Log messages from frontend"""
    logger.info(f"FRONTEND LOG: {request.message}")
    return {"status": "logged"}

def get_agent_service() -> AgentService:
    """Get the agent service, raising an error if not initialized"""
    if agent_service is None:
        raise HTTPException(status_code=500, detail="Agent service not initialized")
    return agent_service

@app.post("/v1/query")
async def create_query(request: QueryRequest):
    """Create a new query and return run_id"""
    service = get_agent_service()
    
    run_id = str(uuid.uuid4())
    logger.info(f"Created query with run_id: {run_id}, query: {request.query}, model: {request.model}")
    
    # Start background task for processing with selected model
    asyncio.create_task(service.process_query(run_id, request.query, request.model))
    
    return {"run_id": run_id}

@app.get("/v1/stream/{run_id}")
async def stream_events(run_id: str):
    """Stream events for a specific run_id"""
    service = get_agent_service()
    
    logger.info(f"Starting stream for run_id: {run_id}")
    
    async def event_generator():
        try:
            async for event in service.get_event_stream(run_id):
                print("SENDING EVENT TO CLIENT:", event)
                sys.stdout.flush()
                yield f"data: {json.dumps(event)}\n\n"
                print("YIELDED EVENT TO CLIENT")
                sys.stdout.flush()
                await asyncio.sleep(0)
                if event.get("type") in ["complete", "error"]:
                    print("YIELDING KEEP-ALIVE AFTER FINAL EVENT")
                    sys.stdout.flush()
                    yield ": keep-alive\n\n"
                    break
        except Exception as e:
            logger.error(f"Error in event stream for {run_id}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            await asyncio.sleep(0)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
