from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from dotenv import load_dotenv
from .graph import build_bot
import os, httpx, json

load_dotenv()
STATE = {}
USER_DOCS: dict[str, str] = {}  # user_id -> document_id of last uploaded PDF

@asynccontextmanager
async def lifespan(app: FastAPI):
    STATE["bot"] = await build_bot()
    yield
    STATE.clear()

RESUME_WORDS = ["resume", "cv", "ats", "score", "job description", "jd", "review my"]
MATH_WORDS = ["add", "plus", "times", "multiply", "calculate", "divide", "minus", "subtract"]
DEPLOYED = os.getenv("RESUME_API_URL")
RAG_DEPLOYED = os.getenv("RAG_API_URL")

app = FastAPI(title="Smart Chatbot", lifespan=lifespan)

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def call_deployed(endpoint: str, file_bytes: bytes, filename: str, jd: str):
    if not DEPLOYED:
        raise RuntimeError("RESUME_API_URL is not set")
    async with httpx.AsyncClient(timeout=60) as client:
        files = {"file": (filename, file_bytes, "application/pdf")}
        data = {"job_description": jd}
        r = await client.post(f"{DEPLOYED.rstrip('/')}{endpoint}", files=files, data=data)
        r.raise_for_status()
        return r.json()


async def upload_to_rag(file_bytes: bytes, filename: str) -> dict:
    if not RAG_DEPLOYED:
        raise RuntimeError("RAG_API_URL is not set")
    async with httpx.AsyncClient(timeout=60) as client:
        files = {"file": (filename, file_bytes, "application/pdf")}
        r = await client.post(f"{RAG_DEPLOYED.rstrip('/')}/upload-file/", files=files)
        r.raise_for_status()
        return r.json()


async def ask_rag(document_id: str, question: str) -> str:
    if not RAG_DEPLOYED:
        raise RuntimeError("RAG_API_URL is not set")
    answer = ""
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST", f"{RAG_DEPLOYED.rstrip('/')}/chat/",
            json={"document_id": document_id, "question": question},
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("type") == "text":
                    answer += chunk.get("content", "")
    return answer


async def run_bot(message: str, user_id: str):
    cfg = {"configurable": {"thread_id": user_id}}
    out = await STATE["bot"].ainvoke(
        {"messages": [{"role": "user", "content": message}]}, cfg)
    return out["messages"][-1].content


@app.post("/chat")
async def chat(message: str = Form(...), user_id: str = Form("default"),
               file: Optional[UploadFile] = File(None),
               job_description: Optional[str] = Form(None)):

    # ---- no file → normal chat, or follow-up on a previously uploaded PDF ----
    if file is None:
        is_math = any(w in message.lower() for w in MATH_WORDS)
        if not is_math and user_id in USER_DOCS:
            try:
                reply = await ask_rag(USER_DOCS[user_id], message)
            except httpx.HTTPError as e:
                return {"reply": f"RAG service error: {e}", "mode": "error"}
            except RuntimeError as e:
                return {"reply": str(e), "mode": "error"}
            return {"reply": reply, "mode": "rag"}
        return {"reply": await run_bot(message, user_id), "mode": "chat"}

    # ---- file present: validate ----
    if file.content_type != "application/pdf":
        return {"reply": "Please upload a PDF file.", "mode": "error"}
    contents = await file.read()
    if len(contents) > 10_000_000:                      # ~10 MB cap
        return {"reply": "File too large (max 10 MB).", "mode": "error"}

    is_resume = job_description is not None or any(
        w in message.lower() for w in RESUME_WORDS)

    # ---- resume lane → relay whole PDF to the deployed analyzer ----
    if is_resume:
        jd = job_description or message
        endpoint = "/ats-score" if any(w in message.lower()
                      for w in ["ats", "score"]) else "/review"
        try:
            result = await call_deployed(endpoint, contents, file.filename, jd)
        except httpx.HTTPError as e:
            return {"reply": f"Resume service error: {e}", "mode": "error"}
        except RuntimeError as e:
            return {"reply": str(e), "mode": "error"}
        return {"reply": result, "mode": endpoint.strip("/")}

    # ---- non-resume PDF → upload to the RAG service, then answer this message against it ----
    try:
        uploaded = await upload_to_rag(contents, file.filename)
        USER_DOCS[user_id] = uploaded["document_id"]
        reply = await ask_rag(USER_DOCS[user_id], message or "Summarize this document.")
    except httpx.HTTPError as e:
        return {"reply": f"RAG service error: {e}", "mode": "error"}
    except RuntimeError as e:
        return {"reply": str(e), "mode": "error"}
    return {"reply": reply, "mode": "rag"}


@app.get("/health")
def health():
    return {"status": "ok"}