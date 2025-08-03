import os, time, requests
from datetime import datetime
import streamlit as st
from transformers import pipeline
import firebase_admin
from firebase_admin import credentials, db

# ====== FIREBASE CONFIGURATION ======
if not firebase_admin._apps:
    firebase_config = dict(st.secrets["firebase"])
    firebase_config["private_key"] = firebase_config["private_key"].replace("\\n", "\n")
    cred = credentials.Certificate(firebase_config)
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://test-45718-default-rtdb.firebaseio.com/'
    })

# ====== STREAMLIT CONFIGURATION ======
st.set_page_config(page_title="🪞 Reflective AI", layout="wide")
st.title("🤖 Reflective AI Companion")
st.markdown("Track your thoughts, moods, and patterns over time.")

# ====== OPENROUTER CONFIG ======
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or "YOUR_API_KEY"
MODEL_NAME = "deepseek/deepseek-chat-v3-0324:free"

# ====== SENTIMENT ANALYZER ======
sentiment_pipeline = pipeline("sentiment-analysis")

# ====== USER SETUP ======
with st.sidebar:
    st.header("👤 User Login")
    username = st.text_input("Enter your name to start:")
    if st.button("🔁 Start New Session"):
        st.session_state.clear()
        st.rerun()

# ====== FIREBASE HELPERS ======
def get_user_ref(username):
    return db.reference(f"/users/{username.lower().strip()}")

def load_user_memory(username):
    user_ref = get_user_ref(username)
    data = user_ref.get()
    return data if data else []

def save_to_user_memory(username, entry):
    user_ref = get_user_ref(username)
    memory = load_user_memory(username)
    memory.append(entry)
    user_ref.set(memory)

def summarize_user_patterns(memory):
    sentiments = [m["sentiment"] for m in memory]
    topics = [t for m in memory for t in m.get("topics", [])]
    most_common_sentiment = max(set(sentiments), key=sentiments.count) if sentiments else "neutral"
    frequent_topics = list(set(topics))[:3] if topics else []
    return f"User tends to be {most_common_sentiment} and often talks about: {', '.join(frequent_topics)}."

# ====== OPENROUTER ASK FUNCTION ======
def ask_reflective_ai(user_context, user_input, history, lang="English"):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://chat.openai.com",
        "X-Title": "Reflective Chatbot"
    }
    messages = [
        {"role": "system", "content": f"You're a reflective, friendly assistant. Respond in {lang}. Personal context: {user_context}"}
    ]
    for h in history[-3:]:
        messages.append({"role": "user", "content": h["question"]})
        messages.append({"role": "assistant", "content": h["answer"]})
    messages.append({"role": "user", "content": user_input})

    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json={"model": MODEL_NAME, "messages": messages})
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ API Error: {e}"

# ====== MAIN CHAT LOGIC ======
if username:
    st.success(f"👋 Hello {username.title()}! Start chatting below.")
    memory = load_user_memory(username)
    context_summary = summarize_user_patterns(memory)

    if "chat" not in st.session_state:
        st.session_state.chat = []

    query = st.chat_input("💬 What's on your mind today?")
    if query:
        with st.spinner("Reflecting..."):
            sentiment = sentiment_pipeline(query)[0]["label"].lower()
            response = ask_reflective_ai(context_summary, query, st.session_state.chat)

            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "question": query,
                "answer": response,
                "sentiment": sentiment,
                "topics": []  # for future NLP topic extraction
            }
            st.session_state.chat.append(log_entry)
            save_to_user_memory(username, log_entry)

    for chat in reversed(st.session_state.chat):
        with st.chat_message("user"):
            st.markdown(chat["question"])
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            animated = ""
            for c in chat["answer"]:
                animated += c
                response_placeholder.markdown(animated + "|")
                time.sleep(0.005)
            response_placeholder.markdown(animated)

    with st.sidebar:
        st.subheader("🗂️ Your Reflections")
        for chat in reversed(memory[-5:]):
            st.markdown(f"**{chat['timestamp'].split('T')[0]}**")
            st.markdown(f"🧠 *{chat['question']}*\n💬 {chat['answer'][:150]}...")
            st.markdown(f"😶 Sentiment: `{chat['sentiment']}`")
            st.markdown("---")
else:
    st.warning("👤 Please enter your name in the sidebar to begin.")
