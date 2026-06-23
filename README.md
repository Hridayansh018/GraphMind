# GraphMind

A multi-agent chatbot with a FastAPI backend (LangGraph + LangChain) and a static HTML/JS frontend. The bot routes each message to one of three agents — math, web search, or resume review — and can also proxy PDF resumes to a deployed resume-analysis API for ATS scoring and feedback.

## Architecture

```
public/            Static frontend (vanilla JS, deployed to Vercel)
server/
  main.py          Entrypoint — runs uvicorn, reads PORT from env
  app/
    server.py      FastAPI app, routes, lifespan (builds the bot graph on startup)
    graph.py       LangGraph StateGraph — supervisor routes to math/web/resume agents
    agents.py      Agent factories (create_agent) + the OpenRouter LLM client
    tools.py       Weather (Open-Meteo) and web search (Tavily) tools
    doc_tools.py   PDF summarize/ask tools — stubbed out, not yet wired up
  mcp_servers/
    custom_server.py   FastMCP server exposing add/subtract/multiply/divide (math tools)
    resume_mcp.py       FastMCP server exposing review_resume/ats_score, proxies to a
                        deployed resume-analyzer service over HTTP
  utils/           Placeholder modules for a future RAG pipeline (currently empty)
```

### Request flow

1. Frontend POSTs to `/chat` with a message, a `user_id`, and optionally a PDF file +
   job description.
2. If no file is attached, `server.py` calls the LangGraph bot (`graph.py`), which:
   - Spins up two MCP clients over stdio (`custom_server.py` for math, `resume_mcp.py`
     for resume tools) and wraps their tools in LangChain agents (`agents.py`).
   - A `supervisor` node inspects the latest message and routes to `math`, `web`, or
     `resume` based on keywords.
3. If a file is attached, `server.py` instead forwards the PDF + job description
   directly to an external deployed resume-analyzer API (`RESUME_API_URL`) via
   `/review` or `/ats-score`, bypassing the graph.
4. Conversation state is kept per `user_id` using an in-memory LangGraph checkpointer
   (`InMemorySaver`) — history is lost on server restart.

## Requirements

- Python 3.13
- API keys: see [Environment variables](#environment-variables)

## Setup

```bash
cd server
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Create `server/.env` with the variables below, then run the server:

```bash
python main.py
```

The API will be available at `http://localhost:8000`. Open `public/index.html` in a
browser (or serve it statically) to use the chat UI — `public/config.js` points it at
`http://localhost:8000` by default.

## Environment variables

Set these in `server/.env` (local) or in your hosting provider's dashboard
(production):

| Variable           | Required | Used by                          | Purpose                                                              |
|---------------------|----------|-----------------------------------|-----------------------------------------------------------------------|
| `OPENROUTER_API_KEY` | Yes      | `app/agents.py`                  | Auth for the LLM (`openai/gpt-oss-120b:free` via OpenRouter)          |
| `TAVILY_API_KEY`     | Yes      | `app/tools.py`                   | Web search tool                                                      |
| `RESUME_API_URL`     | Yes, for resume/file uploads | `app/server.py` | Base URL of the deployed resume-analyzer service (`/review`, `/ats-score`) |
| `RAG_API_URL`        | Reserved | —                                 | Not currently read by any code; reserved for the future RAG pipeline |
| `PORT`               | No       | `main.py`                        | Port to bind (defaults to `8000`; Render sets this automatically)    |

## API

| Endpoint      | Method | Body (form-data)                                              | Description                                                  |
|---------------|--------|------------------------------------------------------------------|----------------------------------------------------------------|
| `/chat`       | POST   | `message`, `user_id`, `file` (optional PDF), `job_description` (optional) | Routes to the agent graph, or to the resume API if a file is attached |
| `/health`     | GET    | —                                                                  | Liveness check, returns `{"status": "ok"}`                    |

## Frontend

`public/` is a static site (no build step) that talks to the backend via
`window.SERVER_URL` (set in `public/config.js`). It's configured for Vercel deployment
via `public/vercel.json`, which rewrites `config.js` from a `SERVER_URL` env var at
build time.

## Known gaps

- `app/doc_tools.py` (PDF summarize/Q&A) and `utils/*.py` (RAG pipeline) are stubs —
  the functions are unimplemented placeholders.
- Conversation memory is in-process (`InMemorySaver`), so it resets on every deploy or
  restart.
- `mcp_servers/resume_mcp.py` reads uploaded PDFs from `UPLOAD_DIR` by `doc_id`, but
  nothing in the current code path writes files there — the resume flow in
  `server.py` instead forwards the file directly to `RESUME_API_URL`.

## Deploying the backend on Render

1. Create a new **Web Service** on Render, pointed at this repository.
2. **Root Directory:** `server` (required — `main.py` and the MCP servers resolve
   paths like `mcp_servers/custom_server.py` relative to this directory).
3. **Build Command:**
   ```
   pip install -r requirements.txt
   ```
4. **Start Command:**
   ```
   python main.py
   ```
5. Add the environment variables from the table above (`OPENROUTER_API_KEY`,
   `TAVILY_API_KEY`, `RESUME_API_URL`) in the Render dashboard's *Environment* tab.
   Render sets `PORT` automatically — `main.py` already reads it.

## Deploying the frontend on Vercel

`public/vercel.json` is already configured: set the `SERVER_URL` environment variable
in Vercel to your deployed Render backend URL, and Vercel's build command will
generate `config.js` to point at it.
