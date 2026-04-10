from flask import Flask, render_template, jsonify, request, session
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from src.prompt import *
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

load_dotenv()

PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
os.environ["GROQ_API_KEY"] = GROQ_API_KEY

embeddings = download_hugging_face_embeddings()

index_name = "medical-chatbot"

docsearch = PineconeVectorStore.from_existing_index(
    index_name=index_name,
    embedding=embeddings
)

retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 3})

# chatModel = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0.3)
# chatModel = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)   
chatModel = ChatGroq(model="llama-3.1-8b-instant", temperature=0.3)  

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ]
)

question_answer_chain = create_stuff_documents_chain(chatModel, prompt)
rag_chain = create_retrieval_chain(retriever, question_answer_chain)

@app.route('/')
def index():
    session['chat_history'] = []  # reset history on page load
    return render_template('chat.html')

@app.route('/get', methods=['GET', 'POST'])
def chat():
    msg = request.form["msg"]

    # Get chat history from session
    chat_history = []
    for item in session.get('chat_history', []):
        if item['role'] == 'human':
            chat_history.append(HumanMessage(content=item['content']))
        else:
            chat_history.append(AIMessage(content=item['content']))

    # Invoke chain with history
    response = rag_chain.invoke({
        "input": msg,
        "chat_history": chat_history
    })

    answer = response["answer"]

    # Save to session history
    history = session.get('chat_history', [])
    history.append({'role': 'human', 'content': msg})
    history.append({'role': 'ai', 'content': answer})
    session['chat_history'] = history

    print("Question:", msg)
    print("Answer:", answer)
    return str(answer)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)