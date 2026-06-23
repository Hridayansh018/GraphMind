import os, httpx
from fastmcp import FastMCP

mcp = FastMCP("ResumeServer")
BASE = "https://resume-analyzer-henna-gamma.vercel.app"
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/uploads")

def _path(doc_id: str) -> str:
    return os.path.join(UPLOAD_DIR, f"{doc_id}.pdf")

@mcp.tool
def review_resume(doc_id: str, job_description: str) -> dict:
    """Review an uploaded resume against a job description.
    Pass the doc_id exactly as given in the message."""
    with open(_path(doc_id), "rb") as f:
        files = {"file": (f"{doc_id}.pdf", f, "application/pdf")}
        r = httpx.post(f"{BASE}/review", files=files,
                       data={"job_description": job_description}, timeout=60)
    r.raise_for_status()
    return r.json()

@mcp.tool
def ats_score(doc_id: str, job_description: str) -> dict:
    """Get the ATS match score for an uploaded resume against a job description.
    Pass the doc_id exactly as given in the message."""
    with open(_path(doc_id), "rb") as f:
        files = {"file": (f"{doc_id}.pdf", f, "application/pdf")}
        r = httpx.post(f"{BASE}/ats-score", files=files,
                       data={"job_description": job_description}, timeout=60)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    mcp.run()