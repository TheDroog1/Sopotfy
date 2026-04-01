import os
import subprocess
import uuid
import asyncio
import json
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

def run_yt_dlp_cli(video_id: str, output_path: str):
    """
    Usa il comando CLI ufficiale di Homebrew (/opt/homebrew/bin/yt-dlp)
    per garantire velocità massima e risoluzione delle firme con Deno.
    """
    yt_dlp_path = "/opt/homebrew/bin/yt-dlp"
    if not os.path.exists(yt_dlp_path):
        yt_dlp_path = "yt-dlp" # Fallback a path standard se non brew

    # Costruisce il comando
    cmd = [
        yt_dlp_path,
        "--cookies", "cookies.txt" if os.path.exists("cookies.txt") else None,
        "--format", "ba[ext=m4a]/ba[ext=webm]/ba/b",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "192K",
        "--output", f"{output_path}.%(ext)s",
        "--no-warnings",
        "--quiet",
        "--nocheck-certificate",
        "--remote-components", "ejs:github",
        f"https://www.youtube.com/watch?v={video_id}"
    ]
    # Rimuove None se non ci sono cookies
    cmd = [c for c in cmd if c is not None]

    print(f"[CLI SERVER] Esecuzione: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"Errore CLI: {result.stderr}")
    return True

def process_download(video_id: str):
    """
    Background Task: Scaricamento audio tramite CLI e caricamento su Supabase.
    """
    if not supabase:
        print("[DOWNLOAD] Error: Supabase ready.")
        return

    output_filename = f"/tmp/{video_id}"
    final_mp3 = f"{output_filename}.mp3"
    
    try:
        # 1. Scaricamento via CLI (Il modo più veloce esistente su Mac)
        run_yt_dlp_cli(video_id, output_filename)
        
        # 2. Verifica esistenza file
        if not os.path.exists(final_mp3):
            # yt-dlp a volte aggiunge l'estensione nel log ma il file ha nomi diversi
            # Cerchiamo qualsiasi file .mp3 che inizi con l'id
            print(f"[DOWNLOAD] File {final_mp3} non trovato, controllo alternativi...")
            found = False
            for f in os.listdir("/tmp"):
                if f.startswith(video_id) and f.endswith(".mp3"):
                    os.rename(f"/tmp/{f}", final_mp3)
                    found = True
                    break
            if not found:
                raise Exception("Il file MP3 non è stato generato.")

        # 3. Upload a Supabase
        with open(final_mp3, "rb") as f:
            supabase.storage.from_(BUCKET_NAME).upload(
                file=f,
                path=f"{video_id}.mp3",
                file_options={"content-type": "audio/mpeg", "x-upsert": "true"}
            )

        storage_url = supabase.storage.from_(BUCKET_NAME).get_public_url(f"{video_id}.mp3")
        supabase.table("downloads").update({
            "status": "ready",
            "storage_url": storage_url
        }).eq("video_id", video_id).execute()
        
        print(f"[DOWNLOAD] Successo: {video_id}")

    except Exception as e:
        print(f"[DOWNLOAD ERROR] {video_id}: {str(e)}")
        supabase.table("downloads").update({"status": f"failed: {str(e)}"}).eq("video_id", video_id).execute()
    finally:
        if os.path.exists(final_mp3):
            os.remove(final_mp3)

@app.get("/search")
async def search(q: str):
    """
    Ricerca via CLI (Solo metadati, veloce).
    """
    try:
        yt_dlp_path = "/opt/homebrew/bin/yt-dlp" if os.path.exists("/opt/homebrew/bin/yt-dlp") else "yt-dlp"
        cmd = [
            yt_dlp_path,
            "--quiet",
            "--extract-flat",
            "--dump-single-json",
            f"ytsearch10:{q}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(result.stderr)
            
        data = json.loads(result.stdout)
        results = []
        for entry in data.get('entries', []):
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
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/download")
async def download(request: DownloadRequest, background_tasks: BackgroundTasks):
    video_id = request.video_id
    supabase.table("downloads").upsert({
        "video_id": video_id,
        "title": request.title,
        "status": "downloading"
    }).execute()
    
    background_tasks.add_task(process_download, video_id)
    return {"status": "started", "video_id": video_id}

@app.get("/")
def read_root():
    return {"status": "online", "message": "Turbo Server (Homebrew) is active"}
