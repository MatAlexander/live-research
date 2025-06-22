import streamlit as st
import requests
import json
import time
import threading
from datetime import datetime

# Page config
st.set_page_config(
    page_title="AI Thinking Agent",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #2E86AB;
        margin-bottom: 30px;
    }
    .thought-bubble {
        background-color: #f0f8ff;
        border-left: 4px solid #2E86AB;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .final-answer {
        background-color: #e8f5e8;
        border-left: 4px solid #28a745;
        padding: 15px;
        margin: 15px 0;
        border-radius: 5px;
        font-weight: bold;
    }
    .token-stream {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
        font-family: monospace;
        font-size: 12px;
        max-height: 200px;
        overflow-y: auto;
    }
    .status-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-thinking { background-color: #ffa500; }
    .status-complete { background-color: #28a745; }
    .status-error { background-color: #dc3545; }
</style>
""", unsafe_allow_html=True)

def check_backend_health():
    """Check if backend is running"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def create_query(query_text, model="o4-mini"):
    """Create a new query"""
    try:
        response = requests.post(
            "http://localhost:8000/v1/query",
            json={"query": query_text, "model": model},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()['run_id']
        return None
    except Exception as e:
        st.error(f"Failed to create query: {e}")
        return None

def stream_events(run_id):
    """Stream events from backend"""
    try:
        url = f"http://localhost:8000/v1/stream/{run_id}"
        response = requests.get(url, stream=True, timeout=120)
        
        if response.status_code != 200:
            return
        
        buffer = ""
        for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
            if chunk:
                buffer += chunk
                
                while '\n\n' in buffer:
                    line, buffer = buffer.split('\n\n', 1)
                    
                    if line.startswith('data: '):
                        try:
                            event_data = json.loads(line[6:])
                            yield event_data
                        except json.JSONDecodeError:
                            continue
                    elif line.startswith(': '):
                        # Keep-alive, ignore
                        continue
    except Exception as e:
        st.error(f"Streaming error: {e}")

def main():
    # Header
    st.markdown('<h1 class="main-header">🧠 AI Thinking Agent</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666;">Watch AI think in real-time with OpenAI o4-mini</p>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Backend status
        if check_backend_health():
            st.markdown('<div class="status-indicator status-complete"></div>Backend: Connected', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-indicator status-error"></div>Backend: Disconnected', unsafe_allow_html=True)
            st.error("Please start the backend:\n```\ncd backend && python -m uvicorn main:app --reload\n```")
            return
        
        st.divider()
        
        # Model selection
        model = st.selectbox(
            "🤖 AI Model",
            ["o4-mini", "gpt-4", "gpt-3.5-turbo"],
            index=0
        )
        
        # Query examples
        st.subheader("💡 Example Queries")
        example_queries = [
            "What is quantum computing?",
            "Explain machine learning in simple terms",
            "How does blockchain work?",
            "What is the theory of relativity?",
            "Explain photosynthesis step by step"
        ]
        
        for query in example_queries:
            if st.button(f"📝 {query}", key=f"example_{hash(query)}"):
                st.session_state.query_input = query
    
    # Main interface
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Query input
        query = st.text_area(
            "🔍 Ask your question:",
            value=st.session_state.get('query_input', ''),
            height=100,
            placeholder="Enter your question here... (e.g., 'Explain quantum superposition')"
        )
        
        col_submit, col_clear = st.columns([1, 1])
        with col_submit:
            submit_button = st.button("🚀 Ask AI", type="primary", use_container_width=True)
        with col_clear:
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state.clear()
                st.rerun()
    
    with col2:
        st.subheader("📊 Session Stats")
        if 'stats' not in st.session_state:
            st.session_state.stats = {'queries': 0, 'thoughts': 0, 'tokens': 0}
        
        stats = st.session_state.stats
        st.metric("Queries Asked", stats['queries'])
        st.metric("Thoughts Captured", stats['thoughts'])
        st.metric("Tokens Streamed", stats['tokens'])
    
    # Processing and results
    if submit_button and query.strip():
        # Initialize session state
        if 'current_run' not in st.session_state:
            st.session_state.current_run = None
        
        # Update stats
        st.session_state.stats['queries'] += 1
        
        # Create placeholders for dynamic updates
        status_placeholder = st.empty()
        thoughts_placeholder = st.empty()
        tokens_placeholder = st.empty()
        final_answer_placeholder = st.empty()
        
        # Show processing status
        with status_placeholder:
            st.markdown('<div class="status-indicator status-thinking"></div>🤔 AI is thinking...', unsafe_allow_html=True)
        
        # Create query
        run_id = create_query(query, model)
        
        if run_id:
            st.session_state.current_run = run_id
            
            # Stream processing
            thoughts = []
            tokens = []
            final_answer = ""
            start_time = time.time()
            
            # Stream events
            for event in stream_events(run_id):
                event_type = event.get('type', '')
                event_text = event.get('text', '')
                
                if event_type == 'thought':
                    thoughts.append({
                        'text': event_text,
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    })
                    st.session_state.stats['thoughts'] += 1
                    
                    # Update thoughts display
                    with thoughts_placeholder:
                        st.subheader("💭 AI Thoughts")
                        for i, thought in enumerate(thoughts, 1):
                            st.markdown(f'''
                            <div class="thought-bubble">
                                <strong>Thought {i}</strong> <small>({thought['timestamp']})</small><br>
                                {thought['text']}
                            </div>
                            ''', unsafe_allow_html=True)
                
                elif event_type == 'token':
                    tokens.append(event_text)
                    st.session_state.stats['tokens'] += 1
                    
                    # Update token stream (show last 100 tokens)
                    with tokens_placeholder:
                        recent_tokens = tokens[-100:] if len(tokens) > 100 else tokens
                        token_text = ''.join(recent_tokens)
                        
                        st.subheader("🔤 Token Stream")
                        st.markdown(f'''
                        <div class="token-stream">
                            <strong>Live tokens ({len(tokens)} total):</strong><br>
                            {token_text}
                        </div>
                        ''', unsafe_allow_html=True)
                
                elif event_type == 'final_answer':
                    final_answer = event_text
                    
                    # Update final answer
                    with final_answer_placeholder:
                        st.markdown(f'''
                        <div class="final-answer">
                            <h3>🎯 Final Answer</h3>
                            {final_answer}
                        </div>
                        ''', unsafe_allow_html=True)
                
                elif event_type == 'complete':
                    elapsed_time = time.time() - start_time
                    
                    # Update status to complete
                    with status_placeholder:
                        st.markdown(f'''
                        <div class="status-indicator status-complete"></div>
                        ✅ Complete! ({elapsed_time:.1f}s, {len(thoughts)} thoughts, {len(tokens)} tokens)
                        ''', unsafe_allow_html=True)
                    
                    # Show completion summary
                    st.success(f"🎉 AI completed processing in {elapsed_time:.1f} seconds!")
                    break
                
                elif event_type == 'error':
                    with status_placeholder:
                        st.markdown('<div class="status-indicator status-error"></div>❌ Error occurred', unsafe_allow_html=True)
                    st.error(f"Error: {event_text}")
                    break
        else:
            st.error("Failed to create query. Please check the backend connection.")
    
    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #666; margin-top: 50px;">
        <p>🚀 AI Thinking Agent powered by OpenAI o4-mini</p>
        <p>Watch AI reasoning in real-time • Built with FastAPI & Streamlit</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
