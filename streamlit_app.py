import streamlit as st
import requests
import json
import uuid
import time
import textwrap

st.set_page_config(page_title="Live-Thought Debug", layout="wide")

st.title("Live-Thought – Streamlit Debug UI")

backend_url = st.sidebar.text_input("Backend base URL", "http://localhost:8000")

query = st.text_input("Ask a research question")

start_btn = st.button("Submit", type="primary")

status = st.empty()
thoughts_area = st.container()
answer_area = st.container()

if start_btn and query.strip():
    status.info("Sending query…")
    try:
        r = requests.post(f"{backend_url}/v1/query", json={"query": query}, timeout=10)
        r.raise_for_status()
        run_id = r.json()["run_id"]
    except Exception as e:
        status.error(f"Query failed: {e}")
        st.stop()

    status.success(f"Run ID: {run_id}")

    thoughts = []
    live_buffer = ""

    with requests.get(f"{backend_url}/v1/stream/{run_id}", stream=True) as resp:
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue  # keep-alive
            if not raw.startswith("data: "):
                continue
            try:
                evt = json.loads(raw[6:])
            except json.JSONDecodeError:
                continue

            etype = evt.get("type")
            if etype == "token":
                live_buffer += evt.get("text", "")
                thoughts_area.markdown("*" + live_buffer + " _…_*")
            elif etype == "thought":
                if live_buffer:
                    live_buffer = ""
                thoughts.append(evt["text"])
                thoughts_area.markdown("\n".join([f"- {t}" for t in thoughts]))
            elif etype == "citation":
                pass  # ignore for quick debug
            elif etype == "final_answer":
                answer_area.markdown(evt["text"])
            elif etype == "complete":
                status.success("Complete ✅")
                break
            elif etype == "error":
                status.error(evt.get("message", "Unknown error"))
                break 