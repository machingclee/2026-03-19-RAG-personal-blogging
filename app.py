import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.RAGQuestionAnswerer import RAGQuestionAnswerer
load_dotenv()

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://machingclee.github.io"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/tags", summary="API endpoint to find tags")
async def answer(question: str):

    rag = RAGQuestionAnswerer(retrieval_k=10)
    new_question = rag.rewrite_query(question)
    print("using this question to ask for new tags", new_question)
    tags = rag.find_tag_by_question(new_question)
    return {"tags": tags}


@app.get("/articles", summary="API endpoint to answer questions and return relevant article titles")
async def answer(question: str):

    rag = RAGQuestionAnswerer(retrieval_k=10)
    answer, chunks, tags, rephased_question = rag.answer_question(question)

    titles = [chunk.metadata['title'] for chunk in chunks]
    return {"answer": answer, "titles": titles, "tags": tags, "rephased_question": rephased_question}


@app.get("/", summary="Test endpoint to verify the API is working")
async def root():
    # Example: access environment variable
    env_name = os.getenv("APP_NAME", "FastAPI on Lambda")
    return {"message": f"Hello from {env_name}"}
