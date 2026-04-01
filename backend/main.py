import os
import subprocess
import json
import asyncio
import time
import re
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# --- Config ---
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
BUCKET_NAME = "audio-downloads"

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[STARTUP] Supabase client initialized.")
    except Exception as e:
        print(f"[STARTUP] Error during Supabase init: {str(e)}")

app = FastAPI(title="Sopotfy API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadRequest(BaseModel):
    video_id: str
    title: str = "Unknown Track"

def broadcast_url_to_supabase():
    if not supabase: return
    try:
        time.sleep(15) # Attesa per stabilizzazione Cloudflare
        cf_log_path = "cf.txt" if os.path.exists("cf.txt") else "backend/cf.txt"
        if os.path.exists(cf_log_path):
            with open(cf_log_path, "r") as f:
                content = f.read()
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", content)
                if match:
                    url = match.group(0)
                    print(f"[SMART CONNECT] Trasmetto URL: {url}")
                    supabase.table("downloads").upsert({
                        "video_id": "BACKEND_URL",
                        "status": "config",
                        "file_url": url,
                        "title": f"Live: {time.ctime()}"
                    }).execute()
    except Exception as e:
        print(f"[SMART CONNECT ERROR] {str(e)}")

def run_yt_dlp_cli(video_id: str, output_path: str):
    yt_dlp_path = "/opt/homebrew/bin/yt-dlp" if os.path.exists("/opt/homebrew/bin/yt-dlp") else "yt-dlp"
    cmd = [
        yt_dlp_path,
        "--cookies", "cookies.txt" if os.path.exists("cookies.txt") else None,
        "--format", "ba[ext=m4a]/ba[ext=webm]/ba/b",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "--output", f"{output_path}.%(ext)s",
        "--no-warnings", "--quiet", "--nocheck-certificate",
        "--remote-components", "ejs:github",
        f"https://www.youtube.com/watch?v={video_id}"
    ]
    subprocess.run([c for c in cmd if c], capture_output=True, text=True)

def process_download(video_id: str):
    if not supabase: return
    output_filename = f"/tmp/{video_id}"
    final_mp3 = f"{output_filename}.mp3"
    try:
        run_yt_dlp_cli(video_id, output_filename)
        if not os.path.exists(final_mp3):
            for f in os.listdir("/tmp"):
                if f.startswith(video_id) and f.endswith(".mp3"):
                    os.rename(f"/tmp/{f}", final_mp3)
                    break
        with open(final_mp3, "rb") as f:
            supabase.storage.from_(BUCKET_NAME).upload(
                file=f, path=f"{video_id}.mp3",
                file_options={"content-type": "audio/mpeg", "x-upsert": "true"}
            )
        storage_url = supabase.storage.from_(BUCKET_NAME).get_public_url(f"{video_id}.mp3")
        supabase.table("downloads").update({"status": "completed", "file_url": storage_url}).eq("video_id", video_id).execute()
    except Exception as e:
        supabase.table("downloads").update({"status": f"failed: {str(e)}"}).eq("video_id", video_id).execute()
    finally:
        if os.path.exists(final_mp3): os.remove(final_mp3)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(asyncio.to_thread(broadcast_url_to_supabase))

@app.get("/search")
async def search(q: str):
    yt_dlp_path = "/opt/homebrew/bin/yt-dlp" if os.path.exists("/opt/homebrew/bin/yt-dlp") else "yt-dlp"
    cmd = [yt_dlp_path, "--quiet", "--extract-flat", "--dump-single-json", f"ytsearch10:{q}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return {"result": [{
        "id": e.get("id"), "title": e.get("title"),
        "thumbnails": [{"url": f"https://i.ytimg.com/vi/{e.get('id')}/hqdefault.jpg"}],
        "channel": {"name": e.get("uploader")}
    } for e in data.get('entries', []) if e]}

@app.post("/download")
async def download(request: DownloadRequest, background_tasks: BackgroundTasks):
    supabase.table("downloads").upsert({"video_id": request.video_id, "title": request.title, "status": "downloading"}).execute()
    background_tasks.add_task(process_download, request.video_id)
    return {"status": "started"}

@app.get("/")
def read_root(): return {"status": "online", "message": "Sopotfy Turbo Smart Connect Ready"}
