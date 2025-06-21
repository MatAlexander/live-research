# Live-Thought Research Assistant

A sophisticated AI-powered research assistant that provides real-time thought streams, comprehensive answers, and citations using Google Search, web scraping, embeddings, and OpenAI's o4-mini model.

## 🚀 Features

- **Real-time Thought Streaming**: Watch the AI think through problems step-by-step
- **Web Research**: Automatic Google Search and web scraping for up-to-date information
- **Smart Citations**: Automatic citation generation with source URLs and favicons
- **Multiple Frontends**: Both Angular web app and Streamlit interface
- **Streaming Responses**: Server-Sent Events (SSE) for real-time updates
- **Embedding Search**: Semantic search through scraped content
- **Dual Interface**: Choose between modern Angular UI or simple Streamlit app

## 🏗️ Architecture

```
live_thought/
├── backend/                 # FastAPI backend
│   ├── models/             # Pydantic schemas
│   ├── services/           # Core services
│   │   ├── agent_service.py      # Main AI agent
│   │   ├── search_service.py     # Google Search
│   │   ├── scraper_service.py    # Web scraping
│   │   └── embedding_service.py  # OpenAI embeddings
│   └── main.py             # FastAPI app
├── frontend/               # Angular frontend
│   ├── src/app/
│   │   ├── services/
│   │   └── components/
│   └── package.json
├── streamlit_test.py       # Streamlit interface
└── docker-compose.yml      # Docker setup
```

## 🛠️ Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **OpenAI o4-mini**: Advanced reasoning model
- **Selenium**: Web scraping with Chrome
- **Google Search API**: Real-time search results
- **PostgreSQL + pgvector**: Vector database for embeddings
- **Server-Sent Events**: Real-time streaming

### Frontend
- **Angular**: Modern web framework
- **TypeScript**: Type-safe JavaScript
- **Angular Material**: UI components
- **Server-Sent Events**: Real-time updates

### Alternative Interface
- **Streamlit**: Simple Python web interface

## 📋 Prerequisites

- Python 3.11+
- Node.js 18+
- Chrome browser (for Selenium)
- OpenAI API key
- Google Search API key (optional)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd live_thought
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables

Create `.env` file in the backend directory:

```env
***REMOVED***
GOOGLE_SEARCH_API_KEY=your_google_api_key_here
GOOGLE_SEARCH_CX=your_custom_search_engine_id
DATABASE_URL=postgresql://user:password@localhost/live_thought
```

### 4. Frontend Setup

```bash
cd frontend
npm install
```

### 5. Run the Application

#### Option A: Full Stack (Angular + FastAPI)

**Terminal 1 - Backend:**
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
```

Access at: http://localhost:4200

#### Option B: Streamlit Interface

```bash
streamlit run streamlit_test.py
```

Access at: http://localhost:8501

## 🎯 Usage

### Simple Queries
For basic questions like "What is 2+2?", the system bypasses web search and provides direct answers.

### Research Queries
For complex questions like "What are the latest developments in quantum computing?":

1. **Search Phase**: Google Search for relevant sources
2. **Scraping Phase**: Extract content from top results
3. **Embedding Phase**: Create semantic embeddings
4. **Analysis Phase**: AI processes information with visible thoughts
5. **Answer Phase**: Comprehensive final answer with citations

## 🔧 Configuration

### Rate Limits
Configure in `backend/services/agent_service.py`:
```python
self.max_google_queries = 5      # Max Google searches per query
self.max_selenium_fetches = 10   # Max web pages scraped
```

### Models
Change the AI model in `.env`:
```env
OPENAI_CHAT_MODEL=o4-mini  # or gpt-4, gpt-3.5-turbo
```

## 📊 API Endpoints

### POST /v1/query
Create a new research query:
```json
{
  "query": "What are the latest developments in quantum computing?",
  "model": "o4-mini"
}
```

### GET /v1/stream/{run_id}
Stream real-time events:
- `thought`: AI reasoning steps
- `tool_use`: Tool usage (search, scraping, etc.)
- `tool_result`: Tool results
- `citation`: Source citations
- `final_answer`: Complete answer
- `complete`: Stream completion

## 🐳 Docker Deployment

```bash
docker-compose up -d
```

## 🔍 Troubleshooting

### Common Issues

1. **Port Conflicts**: Ensure ports 8000, 4200, and 8501 are available
2. **Chrome Driver**: Selenium requires Chrome browser installed
3. **API Keys**: Verify OpenAI and Google API keys are set correctly
4. **Memory Issues**: Reduce `max_selenium_fetches` for lower memory usage

### Debug Mode

Enable detailed logging by setting environment variable:
```env
LOG_LEVEL=DEBUG
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- OpenAI for the o4-mini model
- Google for search capabilities
- FastAPI for the excellent web framework
- Angular team for the frontend framework

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs in `ai_stream_*.log` files
3. Open an issue on GitHub

---

**Note**: This is a research tool. Always verify information from multiple sources and use responsibly.
