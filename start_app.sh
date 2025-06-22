#!/bin/bash

# AI Thinking Agent Launcher
echo "🚀 Starting AI Thinking Agent..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if port is in use
check_port() {
    lsof -ti:$1 >/dev/null 2>&1
}

# Function to start backend
start_backend() {
    echo -e "${BLUE}🔧 Starting FastAPI Backend on port 8000...${NC}"
    cd backend
    
    if check_port 8000; then
        echo -e "${YELLOW}⚠️  Port 8000 already in use. Backend may already be running.${NC}"
    else
        python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
        BACKEND_PID=$!
        echo -e "${GREEN}✅ Backend started (PID: $BACKEND_PID)${NC}"
    fi
    
    cd ..
}

# Function to start streamlit
start_streamlit() {
    echo -e "${BLUE}🎨 Starting Streamlit Frontend on port 8501...${NC}"
    
    if check_port 8501; then
        echo -e "${YELLOW}⚠️  Port 8501 already in use. Streamlit may already be running.${NC}"
    else
        .venv/bin/streamlit run streamlit_app_new.py --server.port 8501 &
        STREAMLIT_PID=$!
        echo -e "${GREEN}✅ Streamlit started (PID: $STREAMLIT_PID)${NC}"
    fi
}

# Function to check backend health
check_backend_health() {
    echo -e "${BLUE}🏥 Checking backend health...${NC}"
    sleep 3
    
    if curl -s http://localhost:8000/health >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is healthy${NC}"
    else
        echo -e "${RED}❌ Backend health check failed${NC}"
    fi
}

# Main execution
echo -e "${YELLOW}🧠 AI Thinking Agent - Startup Script${NC}"
echo "=================================="

# Start backend
start_backend

# Wait a moment
sleep 2

# Check backend health
check_backend_health

# Start streamlit
start_streamlit

# Final status
echo ""
echo -e "${GREEN}🎉 AI Thinking Agent is starting up!${NC}"
echo ""
echo -e "${BLUE}📍 Access Points:${NC}"
echo -e "   🌐 Streamlit App: ${GREEN}http://localhost:8501${NC}"
echo -e "   🔧 Backend API:   ${GREEN}http://localhost:8000${NC}"
echo -e "   📚 API Docs:      ${GREEN}http://localhost:8000/docs${NC}"
echo ""
echo -e "${YELLOW}💡 Usage:${NC}"
echo "   1. Open http://localhost:8501 in your browser"
echo "   2. Enter a question (e.g., 'What is quantum computing?')"
echo "   3. Watch AI think in real-time!"
echo ""
echo -e "${BLUE}🛑 To stop both services:${NC}"
echo "   Press Ctrl+C or run: pkill -f 'uvicorn\\|streamlit'"
echo ""

# Keep script running
wait
