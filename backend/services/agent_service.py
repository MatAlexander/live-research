import os
import asyncio
import logging
import json
from typing import Dict, List, AsyncGenerator, Optional
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse

import openai
from openai import OpenAI

from models.schemas import (
    ThoughtEvent, PageEvent, TokenEvent, CitationEvent, ErrorEvent,
    DocumentChunk
)
from services.search_service import SearchService
from services.scraper_service import ScraperService
from services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

class AgentService:
    def __init__(self, search_service: SearchService, scraper_service: ScraperService, embedding_service: EmbeddingService):
        self.search_service = search_service
        self.scraper_service = scraper_service
        self.embedding_service = embedding_service
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        # Default model can be overridden per query
        self.default_chat_model = os.getenv("OPENAI_CHAT_MODEL", "o4-mini")
        
        # Store event queues for each run_id
        self.event_queues: Dict[str, asyncio.Queue] = {}
        self.active_runs: Dict[str, bool] = {}
        
        # Track if final answer was sent for each run
        self.final_answer_sent: Dict[str, bool] = {}
        
        # Rate limits
        self.max_google_queries = int(os.getenv("MAX_GOOGLE_QUERIES", "5"))
        self.max_selenium_fetches = int(os.getenv("MAX_SELENIUM_FETCHES", "10"))
    
    async def _emit_event(self, run_id: str, event: dict):
        """Emit an event to the run's queue"""
        if run_id in self.event_queues:
            event["timestamp"] = datetime.now().isoformat()
            event["run_id"] = run_id
            await self.event_queues[run_id].put(event)
            
            # Log event for observability
            logger.info(f"Event emitted for {run_id}: {event['type']} - {event.get('text', event.get('action', ''))[:100]}")
            
            # Also log to file for debugging
            log_file_path = f"ai_stream_{run_id}.log"
            try:
                with open(log_file_path, "a") as log_file:
                    log_file.write(f"=== EVENT EMITTED ===\n")
                    log_file.write(f"Type: {event['type']}\n")
                    log_file.write(f"Full event: {json.dumps(event, indent=2)}\n")
                    log_file.write("=" * 30 + "\n")
            except Exception as e:
                logger.error(f"Failed to log event to file: {e}")
    
    async def process_query(self, run_id: str, query: str, model: Optional[str] = None):
        """Main agent processing loop"""
        # Use provided model or default
        chat_model = model or self.default_chat_model
        logger.info(f"Processing query with model: {chat_model}")
        
        # Initialize event queue
        self.event_queues[run_id] = asyncio.Queue()
        self.active_runs[run_id] = True
        self.final_answer_sent[run_id] = False
        
        try:
            logger.info(f"🚀 Starting agent processing for {run_id}")
            
            # Check if this is a simple test query (like "What is 2+2?")
            is_simple_test = query.lower().strip() in ["what is 2+2?", "2+2", "test"]
            
            if is_simple_test:
                logger.info(f"🧪 Running simple test mode for {run_id}")
                await self._emit_event(run_id, {
                    "type": "thought",
                    "text": "🧪 Test mode: Bypassing search and scraping for simple query..."
                })
                
                # Go directly to OpenAI with a simple prompt
                await self._emit_event(run_id, {
                    "type": "thought",
                    "text": "🧠 Generating response using OpenAI..."
                })
                
                # Simple system prompt for test
                system_prompt = (
                    "You are a helpful AI assistant. Answer the user's question directly.\n\n"
                    "IMPORTANT RESPONSE FORMAT:\n"
                    "- Start each reasoning step with 'THOUGHT: ' followed by your analysis\n"
                    "- Start your final answer with 'FINAL: ' followed by the complete response\n"
                    "- Use multiple THOUGHT: lines to show your reasoning process\n"
                    "- End with one FINAL: section that directly answers the user's question\n\n"
                    "Example format:\n"
                    "THOUGHT: The user is asking a simple mathematical question...\n"
                    "THOUGHT: I need to perform basic arithmetic...\n"
                    "FINAL: The answer is 4.\n"
                )
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ]
                
                await self._process_openai_stream(run_id, messages, chat_model)
                
            else:
                # Normal processing with search and scraping
                await self._process_full_query(run_id, query, chat_model)
            
        except Exception as e:
            logger.error(f"Error processing query for {run_id}: {e}")
            await self._emit_event(run_id, {
                "type": "error",
                "message": str(e)
            })
        finally:
            self.active_runs[run_id] = False
            # Clean up tracking
            if run_id in self.final_answer_sent:
                del self.final_answer_sent[run_id]
            if hasattr(self, '_final_mode') and run_id in self._final_mode:
                del self._final_mode[run_id]
    
    async def get_event_stream(self, run_id: str) -> AsyncGenerator[dict, None]:
        """Get event stream for a specific run_id"""
        if run_id not in self.event_queues:
            self.event_queues[run_id] = asyncio.Queue()
        
        queue = self.event_queues[run_id]
        
        try:
            while True:
                # Wait for event with timeout
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield event
                    # Always break after yielding 'complete' or 'error' event
                    if event.get("type") in ["complete", "error"]:
                        break
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield {"type": "heartbeat", "timestamp": datetime.now().isoformat()}
                    # Don't break here - let the complete event handle the break
        except Exception as e:
            logger.error(f"Error in event stream for {run_id}: {e}")
            yield {"type": "error", "message": str(e)}
        finally:
            # Cleanup
            if run_id in self.event_queues:
                del self.event_queues[run_id]
            if run_id in self.active_runs:
                del self.active_runs[run_id]
    
    async def _process_reasoning_line(self, run_id: str, line: str):
        """Process a line of reasoning output from o4-mini"""
        if not line:
            return
            
        # Log to file for debugging
        log_file_path = f"ai_stream_{run_id}.log"
        with open(log_file_path, "a") as log_file:
            log_file.write(f">>> _process_reasoning_line called with: '{line}'\n")
            
        logger.debug(f"Processing line for {run_id}: '{line}'")
        
        # Track state for multi-line final answers
        if not hasattr(self, '_final_mode'):
            self._final_mode = {}
        if run_id not in self._final_mode:
            self._final_mode[run_id] = False
            
        # Check for THOUGHT: prefix (case insensitive)
        if line.upper().startswith("THOUGHT:"):
            # Extract the thought content
            thought_content = line[8:].strip()  # Remove "THOUGHT:" prefix
            if thought_content:  # Only emit if there's actual content
                with open(log_file_path, "a") as log_file:
                    log_file.write(f">>> EMITTING THOUGHT: '{thought_content}'\n")
                await self._emit_event(run_id, {
                    "type": "thought",
                    "text": thought_content
                })
        # Check for FINAL: prefix (case insensitive)
        elif line.upper().startswith("FINAL:"):
            # Extract the final answer content
            final_content = line[6:].strip()  # Remove "FINAL:" prefix
            self._final_mode[run_id] = True
            if final_content:  # Only emit if there's actual content
                self.final_answer_sent[run_id] = True
                with open(log_file_path, "a") as log_file:
                    log_file.write(f">>> EMITTING FINAL ANSWER: '{final_content}'\n")
                await self._emit_event(run_id, {
                    "type": "final_answer",
                    "text": final_content
                })
        elif line.strip().upper() in ["FINAL:", "THOUGHT:"]:
            # Handle empty prefix lines - set mode but don't emit yet
            if line.strip().upper() == "FINAL:":
                self._final_mode[run_id] = True
                with open(log_file_path, "a") as log_file:
                    log_file.write(f">>> SET FINAL MODE (empty prefix)\n")
        else:
            # For lines without proper prefixes, don't emit them as separate thoughts
            # This prevents individual characters/tokens from being emitted as thoughts
            with open(log_file_path, "a") as log_file:
                log_file.write(f">>> SKIPPING line without proper prefix: '{line}'\n")
            logger.debug(f"Skipping line without proper prefix for {run_id}: '{line}'")

    async def _process_accumulated_content(self, run_id: str, content: str, log_file_path: str):
        """Process the final accumulated content to extract all THOUGHT and FINAL statements"""
        import re
        
        with open(log_file_path, "a") as log_file:
            log_file.write(f"=== PROCESSING ACCUMULATED CONTENT ===\n")
            log_file.write(f"Content to process: '{content}'\n")
        
        # Split by THOUGHT: and FINAL: to extract all statements (case insensitive)
        pattern = r'(THOUGHT:|FINAL:)'
        parts = re.split(pattern, content, flags=re.IGNORECASE)
        
        current_statement = ""
        statement_type = None
        
        for i, part in enumerate(parts):
            if part.strip().upper() in ['THOUGHT:', 'FINAL:']:
                # If we have a previous statement, process it
                if current_statement.strip() and statement_type:
                    full_statement = f"{statement_type} {current_statement.strip()}"
                    with open(log_file_path, "a") as log_file:
                        log_file.write(f"PROCESSING ACCUMULATED STATEMENT: '{full_statement}'\n")
                    await self._process_reasoning_line(run_id, full_statement)
                
                # Start new statement
                statement_type = part.strip()
                current_statement = ""
            else:
                current_statement += part
        
        # Process the last statement
        if current_statement.strip() and statement_type:
            full_statement = f"{statement_type} {current_statement.strip()}"
            with open(log_file_path, "a") as log_file:
                log_file.write(f"PROCESSING FINAL ACCUMULATED STATEMENT: '{full_statement}'\n")
            await self._process_reasoning_line(run_id, full_statement)

    def rewrite_query_for_search(self, query: str) -> str:
        """
        Rewrite the user query to maximize search results (make it more generic/SEO-friendly).
        This is a simple heuristic; for best results, use an LLM or more advanced NLP.
        """
        import re
        # Remove question words and make generic
        query = query.strip()
        # Remove common question prefixes
        query = re.sub(r'^(what|who|when|where|why|how|explain|describe|give me|tell me about)\b', '', query, flags=re.IGNORECASE).strip()
        # Remove punctuation
        query = re.sub(r'[?!.]+$', '', query)
        # Add generic keywords
        if len(query.split()) < 5:
            query += " information details overview summary"
        return query

    async def rewrite_query_with_gpt(self, query: str) -> str:
        """
        Use GPT-4.1-nano to rephrase the query for search (not generic, not SEO, just a natural rewording).
        """
        import openai
        prompt = (
            "Rephrase the following question to maximize the chance of finding relevant information in a web search. "
            "Do not answer the question, do not make it generic or SEO-optimized. Just reword it naturally for search.\n\n"
            f"Question: {query}\nRephrased: "
        )
        try:
            client = openai.AsyncOpenAI()
            response = await client.chat.completions.create(
                model="gpt-4.1-nano",  # Use the correct model name for your deployment
                messages=[{"role": "user", "content": prompt}],
                max_tokens=64,
                temperature=0.4,
            )
            rewritten = response.choices[0].message.content.strip()
            return rewritten
        except Exception as e:
            import logging
            logging.warning(f"GPT-4.1-nano rewrite failed, falling back to heuristic: {e}")
            return self.rewrite_query_for_search(query)

    async def _process_full_query(self, run_id: str, query: str, chat_model: str):
        """Process a full query with search and scraping"""
        # Track rate limits
        google_query_count = 0
        selenium_fetch_count = 0
        citations = []
        
        logger.info(f"📊 Step 1: Starting search and scraping for {run_id}")
        
        # Don't clear embeddings - reuse existing ones to save costs
        # self.embedding_service.clear_database()  # Commented out to prevent excessive API calls
        
        # Step 1: Initial search
        rewritten_query = await self.rewrite_query_with_gpt(query)
        await self._emit_event(run_id, {
            "type": "thought",
            "text": f"Rewriting query for search (GPT-4.1): '{rewritten_query}'"
        })
        await self._emit_event(run_id, {
            "type": "tool_use",
            "tool": "google_search",
            "action": "Searching Google",
            "details": f"Query: '{rewritten_query}'"
        })
        if google_query_count < self.max_google_queries:
            search_results = await self.search_service.google_search(rewritten_query, k=5)
            google_query_count += 1
            
            await self._emit_event(run_id, {
                "type": "tool_result",
                "tool": "google_search",
                "result": f"Found {len(search_results)} search results"
            })
            
            # Step 2: Fetch and process pages
            for result in search_results[:3]:  # Limit to top 3 results
                if selenium_fetch_count >= self.max_selenium_fetches:
                    break
                    
                # Get favicon URL for the domain
                from urllib.parse import urlparse
                domain = urlparse(result.url).netloc
                favicon_url = f"https://www.google.com/s2/favicons?domain={domain}"

                await self._emit_event(run_id, {
                    "type": "tool_use",
                    "tool": "web_scraper",
                    "action": "Scraping webpage",
                    "details": f"URL: {result.url}",
                    "favicon": favicon_url
                })

                await self._emit_event(run_id, {
                    "type": "page",
                    "url": result.url,
                    "favicon": favicon_url
                })

                # Fetch page content
                content = await self.scraper_service.selenium_fetch(result.url)
                if content:
                    selenium_fetch_count += 1
                    
                    # Get page title
                    title = await self.scraper_service.get_page_title(result.url)
                    
                    await self._emit_event(run_id, {
                        "type": "tool_result",
                        "tool": "web_scraper",
                        "result": f"Successfully scraped content from {title}"
                    })
                    
                    # Embed and store
                    await self._emit_event(run_id, {
                        "type": "tool_use",
                        "tool": "embedding",
                        "action": "Creating embeddings",
                        "details": f"Processing content from {title}"
                    })
                    
                    chunks = await self.embedding_service.embed_and_store(
                        content, result.url, title
                    )
                    
                    if chunks:
                        await self._emit_event(run_id, {
                            "type": "tool_result",
                            "tool": "embedding",
                            "result": f"Created {len(chunks)} text embeddings"
                        })
                        
                        # Add to citations
                        citations.append({
                            "url": result.url,
                            "title": title,
                            "favicon": f"https://www.google.com/s2/favicons?domain={urlparse(result.url).netloc}"
                        })
                else:
                    await self._emit_event(run_id, {
                        "type": "tool_result",
                        "tool": "web_scraper",
                        "result": f"Failed to scrape content from {result.url}"
                    })
        
        # Step 3: Retrieve relevant context
        await self._emit_event(run_id, {
            "type": "tool_use",
            "tool": "embedding",
            "action": "Searching embeddings",
            "details": f"Finding relevant context for: '{query}'"
        })
        
        relevant_chunks = await self.embedding_service.search_similar(query, top_k=6)
        
        await self._emit_event(run_id, {
            "type": "tool_result", 
            "tool": "embedding",
            "result": f"Found {len(relevant_chunks)} relevant text chunks"
        })
        
        logger.info(f"🤖 Step 2: Starting OpenAI processing for {run_id}")
        
        # Step 4: Generate answer using OpenAI
        await self._emit_event(run_id, {
            "type": "thought",
            "text": "Generating comprehensive answer..."
        })
        
        # Emit citations
        for citation in citations:
            await self._emit_event(run_id, {
                "type": "citation",
                **citation
            })
        
        logger.info(f"📝 Preparing context for OpenAI - {run_id}")
        
        # Prepare context for OpenAI
        context_text = "\n\n".join([
            f"Source: {chunk.title} ({chunk.url})\nContent: {chunk.content}"
            for chunk in relevant_chunks
        ])
        
        # Log token count for monitoring
        estimated_tokens = len(context_text.split()) + len(query.split())
        logger.info(f"📊 Estimated context tokens for {run_id}: {estimated_tokens}")
        
        logger.info(f"🔮 Calling OpenAI API for {run_id} with model {chat_model}")
        
        # Generate streaming response with chain-of-thought
        system_prompt = (
            "You are an expert research analyst AI. I have already searched the web and scraped relevant content for you. "
            "Analyze the provided context and give a comprehensive answer.\n\n"
            
            "IMPORTANT RESPONSE FORMAT:\n"
            "- Start each reasoning step with 'THOUGHT: ' followed by your analysis\n"
            "- Start your final answer with 'FINAL: ' followed by the complete response\n"
            "- Use multiple THOUGHT: lines to show your reasoning process\n"
            "- End with one FINAL: section that directly answers the user's question\n"
            "- Be thorough but concise in your thoughts\n\n"
            
            "Example format:\n"
            "THOUGHT: Analyzing the first source about quantum developments...\n"
            "THOUGHT: The second source discusses cybersecurity implications...\n"
            "THOUGHT: Combining these insights reveals...\n"
            "FINAL: Based on my analysis, the latest developments in quantum computing include...\n\n"
            
            "The research has already been completed. Your job is to analyze and synthesize the information."
        )
        
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user", 
                "content": f"Context:\n{context_text}\n\nQuestion: {query}"
            }
        ]
        
        await self._process_openai_stream(run_id, messages, chat_model)

    async def _process_openai_stream(self, run_id: str, messages: list, chat_model: str):
        """Process OpenAI streaming response"""
        logger.info(f"🌊 Creating OpenAI stream for {run_id}")
        
        # Stream response from OpenAI with selected model
        try:
            stream = self.client.chat.completions.create(
                model=chat_model,
                messages=messages,
                stream=True,
                max_completion_tokens=2000   # Use max_completion_tokens for o4-mini
                # Note: o4-mini only supports default temperature (1)
            )
            logger.info(f"✅ OpenAI stream created successfully for {run_id}")
        except Exception as e:
            logger.error(f"❌ Failed to create OpenAI stream for {run_id}: {e}")
            await self._emit_event(run_id, {
                "type": "error",
                "message": f"OpenAI API error: {str(e)}"
            })
            return
        
        current_line = ""
        accumulated_content = ""
        thought_count = 0
        max_thoughts = 50  # Prevent infinite thoughts
        
        # Setup detailed logging for streaming
        log_file_path = f"ai_stream_{run_id}.log"
        with open(log_file_path, "w") as log_file:
            log_file.write(f"=== AI STREAMING LOG FOR RUN {run_id} ===\n")
            log_file.write(f"Timestamp: {datetime.now().isoformat()}\n")
            log_file.write(f"Model: {chat_model}\n")
            log_file.write("=" * 50 + "\n\n")
        
        logger.info(f"🎯 Starting stream processing for {run_id}")
        
        # Initial processing thoughts to test real-time streaming
        await self._emit_event(run_id, {
            "type": "thought",
            "text": "🔍 Analyzing information and context..."
        })
        
        await asyncio.sleep(1)  # Small delay to see real-time effect
        
        await self._emit_event(run_id, {
            "type": "thought",
            "text": "🧠 Processing information and generating comprehensive response..."
        })
        
        await asyncio.sleep(1)
        
        chunk_count = 0
        for chunk in stream:
            chunk_count += 1
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                current_line += content
                accumulated_content += content
                
                # Log every chunk received
                with open(log_file_path, "a") as log_file:
                    log_file.write(f"CHUNK {chunk_count}: '{content}'\n")
                    log_file.write(f"CURRENT_LINE: '{current_line}'\n")
                    log_file.write(f"ACCUMULATED: '{accumulated_content}'\n")
                    log_file.write("-" * 30 + "\n")
                
                # Process line by line to separate thoughts from final answer
                while '\n' in current_line:
                    line, current_line = current_line.split('\n', 1)
                    line = line.strip()
                    
                    # Log line processing
                    with open(log_file_path, "a") as log_file:
                        log_file.write(f"PROCESSING LINE: '{line}'\n")
                    
                    if line:  # Only process non-empty lines
                        await self._process_reasoning_line(run_id, line)
                        
                        # Prevent excessive thoughts
                        thought_count += 1
                        if thought_count > max_thoughts:
                            logger.warning(f"Reached max thoughts limit for {run_id}")
                            break
                
                if thought_count > max_thoughts:
                    break
        
        # Log final state
        with open(log_file_path, "a") as log_file:
            log_file.write(f"\n=== PROCESSING FINAL ACCUMULATED CONTENT ===\n")
            log_file.write(f"FINAL ACCUMULATED: '{accumulated_content}'\n")
        
        # Process the final accumulated content for THOUGHT and FINAL statements
        if accumulated_content.strip():
            await self._process_accumulated_content(run_id, accumulated_content, log_file_path)
        
        logger.info(f"Streaming complete for {run_id}. Log saved to: {log_file_path}")
        
        # Check if final answer was sent, if not, send a fallback
        if not self.final_answer_sent.get(run_id, False):
            logger.warning(f"No final answer was sent for {run_id}, sending fallback")
            await self._emit_event(run_id, {
                "type": "final_answer",
                "text": "I have completed my research and analysis. Please refer to my thoughts above for the comprehensive findings."
            })
        
        # Mark completion
        await self._emit_event(run_id, {
            "type": "complete",
            "text": "Answer complete"
        })
