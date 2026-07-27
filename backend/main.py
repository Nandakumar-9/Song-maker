import os
import re
import sys
import time
import uuid
import shutil
import zipfile
import asyncio
import tempfile
import traceback
import threading
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import yt_dlp

# Automatically resolve and inject FFmpeg & FFprobe into PATH
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception as e:
    print(f"static_ffmpeg load notice: {e}")

# Fallback check for imageio-ffmpeg if needed
if not shutil.which("ffmpeg"):
    try:
        import imageio_ffmpeg
        img_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        if img_ffmpeg and os.path.exists(img_ffmpeg):
            os.environ["PATH"] = os.path.dirname(img_ffmpeg) + os.path.pathsep + os.environ.get("PATH", "")
    except Exception as err:
        print(f"imageio_ffmpeg load notice: {err}")

FFMPEG_BINARY = shutil.which("ffmpeg")
FFMPEG_AVAILABLE = FFMPEG_BINARY is not None
FFMPEG_WARNING = "" if FFMPEG_AVAILABLE else "FFmpeg was not detected."

# Directories
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
FRONTEND_DIR = BASE_DIR / "frontend"

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="YT Audio Extractor",
    description="YouTube Audio Extractor API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs_lock = threading.Lock()
jobs: Dict[str, Dict[str, Any]] = {}

class ExtractRequest(BaseModel):
    url: str
    quality: Optional[str] = "192"

def clean_filename(name: str) -> str:
    """Sanitize string for safe filenames (Windows-compatible)."""
    # Remove all characters forbidden on Windows filesystems
    name = re.sub(r'[\\/*?":<>|\t\n\r]', "", name)
    # Remove control characters
    name = re.sub(r'[\x00-\x1f\x7f]', "", name)
    # Replace multiple spaces/underscores with single underscore
    name = re.sub(r'[\s]+', "_", name.strip())
    name = re.sub(r'_+', "_", name)
    # Remove trailing dots/spaces (Windows restriction)
    name = name.rstrip('. ')
    # Avoid Windows reserved names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4",
                "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2",
                "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if name.upper() in reserved:
        name = f"_{name}_"
    return name or "audio_track"

def is_valid_youtube_url(url: str) -> bool:
    """Validate YouTube URL format."""
    youtube_regex = r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/(watch\?v=|embed/|v/|playlist\?list=)?[-a-zA-Z0-9@:%_\+.~#?&//=]+$'
    return bool(re.match(youtube_regex, url.strip()))

def run_extraction_job(job_id: str, url: str, target_quality: str):
    """Background worker executing yt-dlp audio extraction."""
    with jobs_lock:
        jobs[job_id]["status"] = "fetching_metadata"
        jobs[job_id]["progress"] = 5.0
        jobs[job_id]["message"] = "Analyzing YouTube video metadata..."

    def progress_hook(d):
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            percent = (downloaded / total_bytes * 100) if total_bytes > 0 else 50.0
            scaled_percent = 10.0 + (percent * 0.75)
            
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            
            with jobs_lock:
                jobs[job_id]["status"] = "downloading"
                jobs[job_id]["progress"] = round(scaled_percent, 1)
                jobs[job_id]["speed"] = speed
                jobs[job_id]["eta"] = eta
                jobs[job_id]["message"] = f"Downloading audio stream ({round(percent, 1)}%)"
        
        elif d['status'] == 'finished':
            with jobs_lock:
                jobs[job_id]["status"] = "converting"
                jobs[job_id]["progress"] = 90.0
                jobs[job_id]["message"] = f"Converting audio to {target_quality}kbps MP3..."

    try:
        ydl_opts_meta = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist' if 'playlist' in url.lower() else False,
        }
        if FFMPEG_BINARY:
            ydl_opts_meta['ffmpeg_location'] = os.path.dirname(FFMPEG_BINARY)

        with yt_dlp.YoutubeDL(ydl_opts_meta) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise ValueError("Could not fetch metadata for this URL. Video may be private or unavailable.")

        is_playlist = 'entries' in info and len(info['entries']) > 1

        if is_playlist:
            entries = info['entries']
            playlist_title = info.get('title', 'Playlist')
            safe_pl_title = clean_filename(playlist_title)
            
            with jobs_lock:
                jobs[job_id]["title"] = f"Playlist: {playlist_title} ({len(entries)} tracks)"
                jobs[job_id]["is_playlist"] = True
                jobs[job_id]["total_items"] = len(entries)

            job_temp_dir = DOWNLOADS_DIR / f"temp_{job_id}"
            job_temp_dir.mkdir(exist_ok=True)

            ydl_opts_pl = {
                'format': 'bestaudio/best',
                'outtmpl': str(job_temp_dir / '%(title).60s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': target_quality,
                }],
            }
            if FFMPEG_BINARY:
                ydl_opts_pl['ffmpeg_location'] = os.path.dirname(FFMPEG_BINARY)

            with yt_dlp.YoutubeDL(ydl_opts_pl) as ydl:
                ydl.download([url])

            zip_filename = f"{safe_pl_title}_{job_id[:8]}.zip"
            zip_path = DOWNLOADS_DIR / zip_filename

            mp3_files = list(job_temp_dir.glob("*.mp3"))
            if not mp3_files:
                raise ValueError("Failed to extract audio files from playlist.")

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for mp3 in mp3_files:
                    zipf.write(mp3, arcname=mp3.name)

            shutil.rmtree(job_temp_dir, ignore_errors=True)

            with jobs_lock:
                jobs[job_id]["status"] = "completed"
                jobs[job_id]["progress"] = 100.0
                jobs[job_id]["message"] = "Playlist processing finished!"
                jobs[job_id]["download_url"] = f"/files/{zip_filename}"
                jobs[job_id]["filename"] = zip_filename
                jobs[job_id]["bitrate"] = f"{target_quality}kbps MP3 (ZIP)"
            return

        # Single video handling
        title = info.get('title', 'Audio Track')
        thumbnail = info.get('thumbnail') or (info.get('thumbnails')[-1]['url'] if info.get('thumbnails') else None)
        duration = info.get('duration', 0)
        channel = info.get('uploader') or info.get('channel', 'YouTube')

        source_abr = info.get('abr') or info.get('audio_bitrate')
        source_codec = info.get('acodec') or info.get('ext')
        sample_rate = info.get('asr') or 44100

        with jobs_lock:
            jobs[job_id]["title"] = title
            jobs[job_id]["thumbnail"] = thumbnail
            jobs[job_id]["duration"] = duration
            jobs[job_id]["channel"] = channel
            jobs[job_id]["bitrate"] = f"{target_quality}kbps MP3"
            jobs[job_id]["source_info"] = f"{source_codec.upper() if source_codec else 'Audio'} ~{int(source_abr) if source_abr else 160}kbps ({sample_rate}Hz)"

        safe_title = clean_filename(title)[:50]
        output_filename = f"{safe_title}_{job_id[:8]}.mp3"
        output_filepath = DOWNLOADS_DIR / output_filename

        # Use a truly safe temp directory (no spaces, no special chars) for yt-dlp/FFmpeg
        # tempfile.mkdtemp creates a randomly-named dir like C:\Users\...\downloads\tmpXXXXXX
        job_temp_dir = tempfile.mkdtemp(dir=str(DOWNLOADS_DIR))
        try:
            ydl_opts_single = {
                'format': 'bestaudio/best',
                # 'audio' is a fixed safe name — no title chars ever touch the temp path
                'outtmpl': os.path.join(job_temp_dir, 'audio.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'progress_hooks': [progress_hook],
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': target_quality,
                }],
                'keepvideo': False,
            }
            if FFMPEG_BINARY:
                ydl_opts_single['ffmpeg_location'] = os.path.dirname(FFMPEG_BINARY)

            with yt_dlp.YoutubeDL(ydl_opts_single) as ydl:
                ydl.download([url])

            # Find the generated mp3 (or any audio file) in the temp dir
            temp_mp3 = os.path.join(job_temp_dir, 'audio.mp3')
            if not os.path.exists(temp_mp3):
                # Fallback: grab whatever was produced
                produced = [f for f in os.listdir(job_temp_dir) if os.path.isfile(os.path.join(job_temp_dir, f))]
                if not produced:
                    raise FileNotFoundError("Output MP3 file was not generated. FFmpeg may be missing or failed.")
                temp_mp3 = os.path.join(job_temp_dir, produced[0])

            # shutil.move works cross-drive and overwrites on Windows (unlike Path.rename)
            if output_filepath.exists():
                output_filepath.unlink()
            shutil.move(temp_mp3, str(output_filepath))
        finally:
            shutil.rmtree(job_temp_dir, ignore_errors=True)

        with jobs_lock:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["progress"] = 100.0
            jobs[job_id]["message"] = "Extraction complete!"
            jobs[job_id]["download_url"] = f"/files/{output_filename}"
            jobs[job_id]["filename"] = output_filename

    except Exception as e:
        err_msg = str(e)
        tb = traceback.format_exc()
        print(f"[EXTRACTION ERROR] job={job_id}\n{tb}", file=sys.stderr, flush=True)
        if "Private video" in err_msg or "Sign in" in err_msg:
            err_msg = "This video is private, age-restricted, or unavailable."
        elif "Incomplete YouTube ID" in err_msg or "is not a valid URL" in err_msg:
            err_msg = "Invalid YouTube URL. Please enter a valid YouTube video or playlist link."
        elif "Errno 22" in err_msg:
            err_msg = f"File system error (Errno 22). Check server logs for details. Raw: {err_msg}"

        with jobs_lock:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = err_msg
            jobs[job_id]["message"] = f"Failed: {err_msg}"

@app.on_event("startup")
async def startup_event():
    print("==================================================")
    print("  YT Audio Extractor - Backend Server Active")
    print(f"  FFmpeg Binary Path: {FFMPEG_BINARY}")
    print(f"  FFmpeg Status: {'[OK] Ready' if FFMPEG_AVAILABLE else '[WARNING] Missing'}")
    print("==================================================")
    asyncio.create_task(periodic_cleanup())

async def periodic_cleanup():
    """Auto-deletes files older than 1 hour (3600 seconds)."""
    while True:
        try:
            now = time.time()
            one_hour_ago = now - 3600
            for file_path in DOWNLOADS_DIR.iterdir():
                if file_path.is_file() and file_path.stat().st_mtime < one_hour_ago:
                    try:
                        file_path.unlink()
                        print(f"[CLEANUP] Deleted old file: {file_path.name}")
                    except Exception as e:
                        print(f"[CLEANUP ERROR] {e}")
        except Exception as err:
            print(f"[CLEANUP LOOP ERROR] {err}")
        
        await asyncio.sleep(600)

@app.get("/api/system-status")
def system_status():
    return {
        "ffmpeg_installed": FFMPEG_AVAILABLE,
        "ffmpeg_path": FFMPEG_BINARY,
        "ffmpeg_warning": FFMPEG_WARNING,
        "downloads_dir": str(DOWNLOADS_DIR)
    }

@app.post("/extract")
@app.post("/api/extract")
def extract_audio(req: ExtractRequest, background_tasks: BackgroundTasks):
    url = req.url.strip()
    if not is_valid_youtube_url(url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL. Please provide a valid YouTube video or playlist link.")

    job_id = str(uuid.uuid4())
    quality = req.quality or "192"
    
    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0.0,
            "speed": "0 KB/s",
            "eta": "--:--",
            "message": "Initializing audio extraction...",
            "created_at": time.time(),
            "url": url,
            "quality": quality,
            "download_url": f"/files/{job_id}.mp3"
        }

    thread = threading.Thread(target=run_extraction_job, args=(job_id, url, quality))
    thread.daemon = True
    thread.start()

    return {"job_id": job_id, "status": "queued", "download_url": f"/files/{job_id}.mp3"}

@app.get("/status/{job_id}")
@app.get("/api/status/{job_id}")
def get_job_status(job_id: str):
    with jobs_lock:
        if job_id not in jobs:
            raise HTTPException(status_code=404, detail="Job not found.")
        return jobs[job_id]

@app.get("/files/{filename}")
@app.get("/api/files/{filename}")
def download_file(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = DOWNLOADS_DIR / safe_filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Requested file has expired or does not exist.")

    media_type = "audio/mpeg" if safe_filename.endswith(".mp3") else "application/zip"
    return FileResponse(
        path=file_path,
        filename=safe_filename,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'}
    )

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
