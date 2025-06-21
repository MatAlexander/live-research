import os
import logging
import sqlite3
import json
from typing import List, Optional
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import openai
from openai import OpenAI, AzureOpenAI

from models.schemas import DocumentChunk

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        # Check if Azure OpenAI configuration is provided
        if os.getenv("AZURE_OPENAI_ENDPOINT"):
            self.client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
            )
            self.embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002")
            self.is_azure = True
            logger.info("Using Azure OpenAI for embeddings")
        else:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            self.embedding_model = "text-embedding-3-small"
            self.is_azure = False
            logger.info("Using OpenAI for embeddings")
            
        self.db_path = "embeddings.db"
        self._init_db()
        
    def _init_db(self):
        """Initialize SQLite database for embeddings"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        
    def _chunk_text(self, text: str, max_tokens: int = 2000) -> List[str]:
        """
        Split text into chunks of approximately max_tokens
        Simple word-based chunking - could be improved with tiktoken
        """
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        # Rough estimate: 1 token ≈ 0.75 words
        max_words = int(max_tokens * 0.75)
        
        for word in words:
            if current_length + 1 > max_words and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_length = 1
            else:
                current_chunk.append(word)
                current_length += 1
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        return chunks
    
    async def embed_and_store(self, content: str, url: str, title: str) -> List[DocumentChunk]:
        """
        Chunk text, generate embeddings, and store in database
        Only creates new embeddings if URL hasn't been processed recently
        """
        try:
            # Check if we already have embeddings for this URL
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM embeddings WHERE url = ?", (url,))
            existing_count = cursor.fetchone()[0]
            conn.close()
            
            if existing_count > 0:
                logger.info(f"URL {url} already has {existing_count} embeddings, reusing existing ones")
                return await self._get_existing_chunks(url)
            
            # Chunk the content
            chunks = self._chunk_text(content)
            logger.info(f"Creating {len(chunks)} new embeddings for {url}")
            
            document_chunks = []
            
            for chunk in chunks:
                if len(chunk.strip()) < 50:  # Skip very short chunks
                    continue
                    
                # Generate embedding
                response = self.client.embeddings.create(
                    model=self.embedding_model,
                    input=chunk
                )
                
                embedding = response.data[0].embedding
                
                # Store in database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO embeddings (content, url, title, embedding)
                    VALUES (?, ?, ?, ?)
                """, (chunk, url, title, json.dumps(embedding)))
                
                conn.commit()
                conn.close()
                
                document_chunks.append(DocumentChunk(
                    content=chunk,
                    url=url,
                    title=title,
                    embedding=embedding
                ))
            
            logger.info(f"Stored {len(document_chunks)} chunks for {url}")
            return document_chunks
            
        except Exception as e:
            logger.error(f"Failed to embed content from {url}: {e}")
            return []
    
    async def search_similar(self, query: str, top_k: int = 8, max_per_domain: int = 2) -> List[DocumentChunk]:
        """
        Search for similar chunks using cosine similarity
        """
        try:
            # Generate query embedding
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=query
            )
            query_embedding = np.array(response.data[0].embedding)
            
            # Retrieve all embeddings from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT content, url, title, embedding FROM embeddings")
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return []
            
            # Calculate similarities
            similarities = []
            for content, url, title, embedding_json in rows:
                embedding = np.array(json.loads(embedding_json))
                similarity = cosine_similarity([query_embedding], [embedding])[0][0]
                
                similarities.append((similarity, DocumentChunk(
                    content=content,
                    url=url,
                    title=title,
                    score=float(similarity)
                )))
            
            # Sort by similarity
            similarities.sort(key=lambda x: x[0], reverse=True)
            
            # Apply domain limits and select top_k
            domain_counts = {}
            selected_chunks = []
            
            for similarity, chunk in similarities:
                if len(selected_chunks) >= top_k:
                    break
                    
                # Extract domain from URL
                from urllib.parse import urlparse
                domain = urlparse(chunk.url).netloc
                
                if domain_counts.get(domain, 0) < max_per_domain:
                    selected_chunks.append(chunk)
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
            
            logger.info(f"Retrieved {len(selected_chunks)} similar chunks for query")
            return selected_chunks
            
        except Exception as e:
            logger.error(f"Failed to search similar chunks: {e}")
            return []
    
    async def _get_existing_chunks(self, url: str) -> List[DocumentChunk]:
        """Retrieve existing chunks for a URL from the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT content, url, title, embedding FROM embeddings WHERE url = ?", (url,))
            rows = cursor.fetchall()
            conn.close()
            
            chunks = []
            for content, url, title, embedding_json in rows:
                embedding = json.loads(embedding_json)
                chunks.append(DocumentChunk(
                    content=content,
                    url=url,
                    title=title,
                    embedding=embedding
                ))
            
            return chunks
            
        except Exception as e:
            logger.error(f"Error retrieving existing chunks for {url}: {e}")
            return []

    def clear_database(self):
        """Clear all embeddings from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM embeddings")
        conn.commit()
        conn.close()
        logger.info("Cleared embeddings database")
