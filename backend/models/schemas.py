from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class QueryRequest(BaseModel):
    query: str
    model: Optional[str] = "o4-mini"

class ThoughtEvent(BaseModel):
    type: str = "thought"
    text: str
    timestamp: Optional[datetime] = None
    run_id: Optional[str] = None

class PageEvent(BaseModel):
    type: str = "page"
    url: str
    title: Optional[str] = None
    timestamp: Optional[datetime] = None
    run_id: Optional[str] = None

class TokenEvent(BaseModel):
    type: str = "token"
    text: str
    timestamp: Optional[datetime] = None
    run_id: Optional[str] = None

class CitationEvent(BaseModel):
    type: str = "citation"
    url: str
    title: str
    favicon: Optional[str] = None
    timestamp: Optional[datetime] = None
    run_id: Optional[str] = None

class ErrorEvent(BaseModel):
    type: str = "error"
    message: str
    timestamp: Optional[datetime] = None
    run_id: Optional[str] = None

class ToolUseEvent(BaseModel):
    type: str = "tool_use"
    tool: str  # "google_search", "web_scraper", "embedding"
    action: str  # Human-readable action description
    details: str  # Additional details about the action
    timestamp: Optional[datetime] = None
    run_id: Optional[str] = None

class ToolResultEvent(BaseModel):
    type: str = "tool_result"
    tool: str  # "google_search", "web_scraper", "embedding"
    result: str  # Human-readable result description
    timestamp: Optional[datetime] = None
    run_id: Optional[str] = None

class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str

class DocumentChunk(BaseModel):
    content: str
    url: str
    title: str
    embedding: Optional[List[float]] = None
    score: Optional[float] = None

class FinalAnswerTokenEvent(BaseModel):
    type: str = "final_answer_token"
    text: str
    timestamp: Optional[datetime] = None
    run_id: Optional[str] = None
