import os
import asyncio
from typing import List
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from youtubesearchpython import VideosSearch
import yt_dlp
from supabase import create_client, Client
from dotenv import load_dotenv

# Load local env if exists
load_dotenv()

# --- Config ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") # Service role for write access
BUCKET_NAME = "audio-downloads"

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

app = FastAPI(title="Sopotfy API")

class DownloadRequest(BaseModel):
    video_id: str

def process_download(video_id: str):
    """
    Background Task: Download audio using yt-dlp, convert to MP3, 
    upload to Supabase and update database.
    """
    if not supabase:
        print("Error: Supabase client not initialized. Check your environment variables.")
        return

    # yt-dlp configuration for audio extraction
    output_filename = f"/tmp/{video_id}"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_filename}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        # 1. Download and Extract
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Note: yt-dlp automatically handles the .mp3 extension during post-processing
            ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
        
        file_path = f"{output_filename}.mp3"
        
        if not os.path.exists(file_path):
            raise Exception("File MP3 non trovato dopo l'elaborazione.")

        # 2. Upload to Supabase Storage
        file_name = f"{video_id}.mp3"
        with open(file_path, "rb") as f:
            supabase.storage.from_(BUCKET_NAME).upload(
                path=file_name,
                file=f,
                file_options={"content-type": "audio/mpeg", "x-upsert": "true"}
            )

        # 3. Get Public URL
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_name)

        # 4. Update Supabase Table 'downloads'
        # We use an upsert/update logic. We assume the table has columns: video_id, status, public_url
        supabase.table("downloads").update({
            "status": "completed",
            "public_url": public_url
        }).eq("video_id", video_id).execute()

        # 5. Clean up
        if os.path.exists(file_path):
            os.remove(file_path)
            
    except Exception as e:
        print(f"Bkg Task Error for {video_id}: {str(e)}")
        try:
            supabase.table("downloads").update({"status": "failed"}).eq("video_id", video_id).execute()
        except:
            pass

@app.get("/search")
async def search(q: str):
    """
    Search YouTube for videos based on the query.
    """
    try:
        videos_search = VideosSearch(q, limit=10)
        results = videos_search.result()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/download")
async def download(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    Initiates a background download task and responds immediately.
    """
    if not supabase:
        raise HTTPException(status_code=400, detail="Supabase not configured")

    # Initial entry to track process
    try:
        supabase.table("downloads").upsert({
            "video_id": request.video_id,
            "status": "processing"
        }).execute()
    except Exception as e:
        print(f"Warning: Failed to create initial download record: {str(e)}")

    # Add task to worker
    background_tasks.add_task(process_download, request.video_id)
    
    return {"status": "elaborazione avviata"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
