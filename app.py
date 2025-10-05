from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_openai import ChatOpenAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from src.prompt import *
import os


# --- Flask App ---
app = Flask(__name__)
load_dotenv()

# --- Required Environment Variables ---
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
if not PINECONE_API_KEY:
    raise ValueError("❌ Missing PINECONE_API_KEY in environment variables.")

os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY

# --- Vector Store Config ---
INDEX_NAME = "medical-chatbot"
embeddings = download_hugging_face_embeddings()

# Load your existing Pinecone index
docsearch = PineconeVectorStore.from_existing_index(
    index_name=INDEX_NAME,
    embedding=embeddings
)

# Retriever to fetch the most relevant docs
retriever = docsearch.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 3}
)

# --- Prompt Template ---
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}")
])


# ---------------- ROUTES ---------------- #

@app.route("/")
def index():
    """Render the chat UI"""
    return render_template("chat.html")


@app.route("/get", methods=["POST"])
def chat():
    """
    Process user input from chat.html.
    The user provides both:
    - msg: the question
    - api_key: their personal OpenAI API key
    """
    msg = (request.form.get("msg") or "").strip()
    user_api_key = (request.form.get("api_key") or "").strip()

    if not msg:
        return jsonify({"error": "Message cannot be empty."}), 400
    if not user_api_key:
        return jsonify({"error": "Please provide your OpenAI API key."}), 400

    try:
        # Create a model instance using the user's API key dynamically
        chat_model = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            api_key=user_api_key
        )

        # Build the question-answer chain dynamically for each user
        question_answer_chain = create_stuff_documents_chain(chat_model, prompt)
        rag_chain = create_retrieval_chain(retriever, question_answer_chain)

        # Run the retrieval + generation pipeline
        response = rag_chain.invoke({"input": msg})
        answer = response.get("answer", "").strip()

        if not answer:
            answer = "⚠️ No answer generated. Please check your API key or try again."

        return answer

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
