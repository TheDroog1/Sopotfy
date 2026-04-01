import os
import asyncio
from typing import List
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

# Add CORS middleware to allow connections from Expo Go and mobile apps
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In produzione puoi restringere questo alle origini ammesse
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DownloadRequest(BaseModel):
    video_id: str
    title: str = "Unknown Track"

def process_download(video_id: str):
    """
    Background Task: Download audio using yt-dlp, convert to MP3, 
    upload to Supabase and update database.
    """
    if not supabase:
        print("Error: Supabase client not initialized. Check your environment variables.")
        return

    # yt-dlp configuration for audio extraction mit stealth options
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
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios'],
                'skip': ['webpage', 'hls', 'dash']
            }
        },
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
        error_msg = str(e)
        print(f"Bkg Task Error for {video_id}: {error_msg}")
        try:
            # We use an upsert-style update to the status column for direct debugging
            supabase.table("downloads").update({"status": f"failed: {error_msg}"}).eq("video_id", video_id).execute()
        except Exception as db_err:
            print(f"CRITICAL: Failed to update DB status: {str(db_err)}")

@app.get("/search")
async def search(q: str):
    """
    Search YouTube using yt-dlp (more stable than other libs).
    """
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'force_generic_extractor': False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # ytsearch10:query searches for 10 results
            info = ydl.extract_info(f"ytsearch10:{q}", download=False)
            
            # Reformat to match what we expected (id, title, thumbnail)
            entries = info.get('entries', [])
            results = []
            for entry in entries:
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
    """
    Initiates a background download task and responds immediately.
    """
    if not supabase:
        raise HTTPException(status_code=400, detail="Supabase not configured")

    # Initial entry to track process
    try:
        supabase.table("downloads").upsert({
            "video_id": request.video_id,
            "status": "processing",
            "title": request.title
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
