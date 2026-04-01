import os
import yt_dlp
import uuid
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
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

print(f"[STARTUP] Checking Supabase URL: {'LOADED' if SUPABASE_URL else 'MISSING'}")
print(f"[STARTUP] Checking Supabase KEY: {'LOADED' if SUPABASE_KEY else 'MISSING'}")

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[STARTUP] Supabase client initialized successfully.")
    except Exception as e:
        print(f"[STARTUP] CRITICAL ERROR during Supabase init: {str(e)}")
else:
    print("[STARTUP] WARNING: Supabase credentials not found in environment.")

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

def get_ydl_opts(mode="android"):
    """
    Returns optimized yt-dlp options based on the chosen mode.
    'android': Best for unauthenticated bypass, no cookies.
    'web': Needs cookies and Node.js (for signatures), high authority.
    """
    output_filename = "/tmp/downloading" # Will be updated per call
    
    base_opts = {
        'format': 'ba[ext=m4a]/ba[ext=webm]/ba/b',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    }
    
    if mode == "android":
        base_opts['extractor_args'] = {'youtube': {'player_client': ['android', 'ios']}}
    else: # web mode with cookies
        base_opts['extractor_args'] = {'youtube': {'player_client': ['web']}}
        if os.path.exists('cookies.txt'):
            base_opts['cookiefile'] = 'cookies.txt'
            
    return base_opts

def process_download(video_id: str):
    """
    Background Task: Tries a two-stage download strategy.
    Phase 1: Android (No cookies, high stealth).
    Phase 2: Web (Cookies + Node.js fallback).
    """
    if not supabase:
        print("[DOWNLOAD] Error: Supabase not ready.")
        return

    output_filename = f"/tmp/{video_id}"
    final_mp3 = f"{output_filename}.mp3"
    
    success = False
    error_msg = ""

    # Phase 1: Try Android (No cookies - bypass signature solving if possible)
    print(f"[DOWNLOAD] Phase 1: Trying Android client for {video_id}...")
    try:
        opts = get_ydl_opts(mode="android")
        opts['outtmpl'] = f'{output_filename}.%(ext)s'
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        success = True
        print(f"[DOWNLOAD] Phase 1 success for {video_id}!")
    except Exception as e:
        error_msg = str(e)
        print(f"[DOWNLOAD] Phase 1 failed: {error_msg}. Retrying with Phase 2...")
        
        # Phase 2: Try Web + Cookies fallback
        try:
            opts = get_ydl_opts(mode="web")
            opts['outtmpl'] = f'{output_filename}.%(ext)s'
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            success = True
            print(f"[DOWNLOAD] Phase 2 success for {video_id} (Cookies used)!")
        except Exception as e2:
            error_msg = str(e2)
            print(f"[DOWNLOAD] Phase 2 failed: {error_msg}")

    if not success:
        supabase.table("downloads").update({"status": f"failed: {error_msg}"}).eq("video_id", video_id).execute()
        return

    # 2. Upload to Supabase Storage
    try:
        file_name = f"{video_id}.mp3"
        with open(final_mp3, "rb") as f:
            supabase.storage.from_(BUCKET_NAME).upload(
                file=f,
                path=file_name,
                file_options={"content-type": "audio/mpeg", "x-upsert": "true"}
            )

        storage_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_name)
        supabase.table("downloads").update({
            "status": "ready",
            "storage_url": storage_url
        }).eq("video_id", video_id).execute()
        
        print(f"[DOWNLOAD] Completed: {video_id}")
    except Exception as e:
        print(f"[UPLOAD ERROR] {video_id}: {str(e)}")
        supabase.table("downloads").update({"status": f"failed_upload: {str(e)}"}).eq("video_id", video_id).execute()
    finally:
        # Cleanup temporary files
        if os.path.exists(final_mp3):
            os.remove(final_mp3)

@app.get("/search")
async def search(q: str):
    """
    Search YouTube using Android client priority (lightest).
    """
    try:
        ydl_opts = get_ydl_opts(mode="android")
        ydl_opts['extract_flat'] = 'in_playlist'
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch10:{q}", download=False)
            results = []
            for entry in info.get('entries', []):
                if entry:
                    results.append({
                        "id": entry.get("id"),
                        "title": entry.get("title"),
                        "thumbnails": [{"url": f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg"}],
                        "channel": {"name": entry.get("uploader")},
                        "url": entry.get("url")
                    })
            return {"result": results}
    except Exception as e:
        print(f"Search Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/download")
async def download(request: DownloadRequest, background_tasks: BackgroundTasks):
    try:
        video_id = request.video_id
        # Create record in DB via service role
        supabase.table("downloads").upsert({
            "video_id": video_id,
            "title": request.title,
            "status": "downloading"
        }).execute()
        
        background_tasks.add_task(process_download, video_id)
        return {"status": "started", "video_id": video_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def read_root():
    return {"status": "online", "message": "Sopotfy Backend is running"}
