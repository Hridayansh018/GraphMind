from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import AsyncIterator, Optional
from dotenv import load_dotenv
from .graph import build_bot
import asyncio, json, os, httpx

load_dotenv()
STATE = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    STATE["bot"] = await build_bot()
    yield
    STATE.clear()

RESUME_WORDS = ["resume", "cv", "ats", "score", "job description", "jd", "review my"]
DEPLOYED = os.getenv("RESUME_API_URL")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

app = FastAPI(title="Smart Chatbot", lifespan=lifespan)

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
        r = await client.post(f"{DEPLOYED}{endpoint}", files=files, data=data)
        r.raise_for_status()
        return r.json()


def sse(event_type: str, **payload) -> bytes:
    return f"data: {json.dumps({'type': event_type, **payload})}\n\n".encode("utf-8")


def sse_response(generator: AsyncIterator[bytes]) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def error_stream(message: str) -> AsyncIterator[bytes]:
    yield sse("error", message=message)
    yield sse("done", mode="error")


async def stream_chat_tokens(message: str, user_id: str) -> AsyncIterator[bytes]:
    cfg = {"configurable": {"thread_id": user_id}}
    full_text = ""
    streamed_any = False
    try:
        async for event in STATE["bot"].astream_events(
            {"messages": [{"role": "user", "content": message}]}, cfg, version="v2"
        ):
            if event["event"] == "on_chat_model_stream":
                text = getattr(event["data"].get("chunk"), "content", "") or ""
                if text:
                    streamed_any = True
                    full_text += text
                    yield sse("token", text=text)
            elif event["event"] == "on_chain_end" and event.get("name") == "LangGraph":
                output = event["data"].get("output")
                if isinstance(output, dict) and output.get("messages"):
                    full_text = output["messages"][-1].content
    except Exception as e:
        yield sse("error", message=str(e))
        yield sse("done", mode="error")
        return

    if not streamed_any and full_text:
        yield sse("token", text=full_text)

    yield sse("done", mode="chat", text=full_text)


async def stream_resume_result(endpoint: str, file_bytes: bytes, filename: str,
                                jd: str, mode: str) -> AsyncIterator[bytes]:
    try:
        result = await call_deployed(endpoint, file_bytes, filename, jd)
    except httpx.HTTPError as e:
        yield sse("error", message=f"Resume service error: {e}")
        yield sse("done", mode="error")
        return
    except RuntimeError as e:
        yield sse("error", message=str(e))
        yield sse("done", mode="error")
        return

    text = result if isinstance(result, str) else json.dumps(result, indent=2)
    words = text.split(" ")
    for i, word in enumerate(words):
        yield sse("token", text=word + (" " if i < len(words) - 1 else ""))
        await asyncio.sleep(0.012)

    yield sse("done", mode=mode, text=text)


@app.post("/chat")
async def chat(message: str = Form(...), user_id: str = Form("default"),
               file: Optional[UploadFile] = File(None),
               job_description: Optional[str] = Form(None)):

    if file is None:
        return sse_response(stream_chat_tokens(message, user_id))

    if file.content_type != "application/pdf":
        return sse_response(error_stream("Please upload a PDF file."))
    contents = await file.read()
    if len(contents) > 10_000_000:                      # ~10 MB cap
        return sse_response(error_stream("File too large (max 10 MB)."))

    is_resume = job_description is not None or any(
        w in message.lower() for w in RESUME_WORDS)

    if is_resume:
        jd = job_description or message
        endpoint = "/ats-score" if any(w in message.lower()
                      for w in ["ats", "score"]) else "/review"
        return sse_response(
            stream_resume_result(endpoint, contents, file.filename, jd, endpoint.strip("/")))

    return sse_response(stream_chat_tokens(message, user_id))


@app.get("/health")
def health():
    return {"status": "ok"}
