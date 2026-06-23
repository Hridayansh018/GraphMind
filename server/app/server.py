from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form
from typing import Optional
from dotenv import load_dotenv
from .graph import build_bot
import os, httpx

load_dotenv()
STATE = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    STATE["bot"] = await build_bot()
    yield
    STATE.clear()

RESUME_WORDS = ["resume", "cv", "ats", "score", "job description", "jd", "review my"]
DEPLOYED = os.getenv("RESUME_API_URL")

app = FastAPI(title="Smart Chatbot", lifespan=lifespan)


async def call_deployed(endpoint: str, file_bytes: bytes, filename: str, jd: str):
    if not DEPLOYED:
        raise RuntimeError("RESUME_API_URL is not set")
    async with httpx.AsyncClient(timeout=60) as client:
        files = {"file": (filename, file_bytes, "application/pdf")}
        data = {"job_description": jd}
        r = await client.post(f"{DEPLOYED}{endpoint}", files=files, data=data)
        r.raise_for_status()
        return r.json()


async def run_bot(message: str, user_id: str):
    cfg = {"configurable": {"thread_id": user_id}}
    out = await STATE["bot"].ainvoke(
        {"messages": [{"role": "user", "content": message}]}, cfg)
    return out["messages"][-1].content


@app.post("/chat")
async def chat(message: str = Form(...), user_id: str = Form("default"),
               file: Optional[UploadFile] = File(None),
               job_description: Optional[str] = Form(None)):

    if file is None:
        return {"reply": await run_bot(message, user_id), "mode": "chat"}

    if file.content_type != "application/pdf":
        return {"reply": "Please upload a PDF file.", "mode": "error"}
    contents = await file.read()
    if len(contents) > 10_000_000:                      # ~10 MB cap
        return {"reply": "File too large (max 10 MB).", "mode": "error"}

    is_resume = job_description is not None or any(
        w in message.lower() for w in RESUME_WORDS)

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

    return {"reply": await run_bot(message, user_id), "mode": "chat"}


@app.get("/health")
def health():
    return {"status": "ok"}
