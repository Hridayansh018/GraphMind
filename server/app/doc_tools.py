# app/doc_tools.py
from langchain_core.tools import tool
# from .rag import load_text, get_store
from .agents import llm

@tool
def summarize_pdf(doc_id: str) -> str:
    """Summarize the uploaded PDF. Pass the doc_id from the message."""
    # text = load_text(doc_id)[:12000]
    # return llm.invoke(f"Summarize this document clearly:\n\n{text}").content
    pass

@tool
def ask_pdf(doc_id: str, question: str) -> str:
    """Answer a question about the uploaded PDF using its content (RAG).
    Pass the doc_id and the user's question."""
    # store = get_store(doc_id)
    # ctx = "\n\n".join(d.page_content for d in store.similarity_search(question, k=4))
    # return llm.invoke(
    #     f"Use only this context to answer.\n\nContext:\n{ctx}\n\nQuestion: {question}"
    # ).content
    pass