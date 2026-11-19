import os, re, uuid, shutil, subprocess
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

BASE = Path(__file__).parent
DOWNLOADS = BASE / "downloads"
DOWNLOADS.mkdir(exist_ok=True)
app = FastAPI(title="ClipFetch")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

JOBS = {}
ALLOWED_SCHEMES = {"http", "https"}

class AnalyzeRequest(BaseModel):
    url: HttpUrl

def validate_url(value: str):
    p = urlparse(value)
    if p.scheme not in ALLOWED_SCHEMES or not p.hostname:
        raise HTTPException(400, "Please enter a valid public HTTP or HTTPS URL.")
    host = p.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith((".local", ".internal")):
        raise HTTPException(400, "Private and local addresses are not supported.")
    return value

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def home():
    return FileResponse(BASE / "static" / "index.html")

@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    url = validate_url(str(req.url))
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-single-json", "--no-warnings", "--no-playlist", url],
            capture_output=True, text=True, timeout=45
        )
        if result.returncode:
            raise HTTPException(422, "Could not read this URL. The site may be unsupported or require access.")
        import json
        info = json.loads(result.stdout)
        formats = []
        seen = set()
        for f in info.get("formats", []):
            if not f.get("url") or not f.get("ext"):
                continue
            height = f.get("height")
            label = (f"{height}p" if height else f.get("format_note") or "Original")
            if f.get("vcodec") == "none":
                label += " · audio"
            elif f.get("acodec") == "none":
                label += " · video only"
            key = (f.get("format_id"), f.get("ext"))
            if key in seen: continue
            seen.add(key)
            formats.append({"id": f.get("format_id"), "label": label, "ext": f.get("ext"),
                            "size": f.get("filesize") or f.get("filesize_approx")})
        formats.sort(key=lambda x: x["label"])
        return {"title": info.get("title", "Media"), "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"), "formats": formats[:60]}
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Analysis timed out. Please try again.")

@app.post("/api/download")
def download(req: dict, background: BackgroundTasks):
    url = validate_url(str(req.get("url", "")))
    fmt = str(req.get("format_id", "best"))
    if not re.fullmatch(r"[A-Za-z0-9_+./,-]{1,80}", fmt):
        raise HTTPException(400, "Invalid format selection.")
    job = uuid.uuid4().hex
    out = DOWNLOADS / job
    out.mkdir()
    JOBS[job] = {"status": "processing", "file": None, "error": None}
    def work():
        try:
            template = str(out / "%(title).100s-%(id)s.%(ext)s")
            p = subprocess.run(["yt-dlp", "--no-playlist", "-f", fmt, "--merge-output-format", "mp4",
                                "--max-filesize", "500M", "-o", template, url], capture_output=True, text=True, timeout=900)
            candidates = [x for x in out.iterdir() if x.is_file()]
            if p.returncode or not candidates:
                JOBS[job] = {"status": "error", "error": "Download failed. Check that you have permission and the selected format is available."}
            else:
                JOBS[job] = {"status": "done", "file": str(candidates[0]), "error": None}
        except Exception:
            JOBS[job] = {"status": "error", "error": "Download failed or timed out."}
    background.add_task(work)
    return {"job_id": job}

@app.get("/api/status/{job_id}")
def status(job_id: str):
    if job_id not in JOBS: raise HTTPException(404, "Job not found")
    j = JOBS[job_id]
    return {"status": j["status"], "error": j["error"]}

@app.get("/api/file/{job_id}")
def get_file(job_id: str):
    j = JOBS.get(job_id)
    if not j or j["status"] != "done" or not j["file"]:
        raise HTTPException(404, "File is not ready")
    path = Path(j["file"])
    return FileResponse(path, filename=path.name, background=BackgroundTasks())
