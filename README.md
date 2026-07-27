# YT Audio Extractor 🎵

A studio-quality YouTube Audio Extractor web application built with **FastAPI**, **yt-dlp**, **FFmpeg**, and modern glassmorphism frontend.

## Key Features

- **320kbps Maximum Quality**: Extract YouTube audio streams at highest available bitrate and convert to 320kbps MP3 (preserving 44.1kHz / 48kHz sample rate).
- **Source Stream Transparency**: Displays actual source codec bitrate (e.g. Opus 160kbps / AAC 128kbps) alongside 320kbps target MP3 conversion specs.
- **Playlist Extraction**: Support for playlist URLs to extract all tracks as audio files and package into a `.zip` archive.
- **Built-in Audio Player Preview**: Listen to processed audio before downloading directly from the UI.
- **Real-Time Progress Tracking**: Live status messages, progress bar, transfer speed, and ETA calculation.
- **Automatic Disk Cleanup**: Downloads folder automatically purges audio files older than 1 hour to conserve disk space.
- **System FFmpeg Auto-Detection**: Friendly UI warning with instant 1-click command copying if FFmpeg is missing.

---

## 🛠️ Prerequisites

### 1. Python
Ensure Python 3.9+ is installed. (Check with `py --version`).

### 2. FFmpeg (Required for MP3 Conversion)
yt-dlp uses FFmpeg to convert YouTube audio streams into MP3 format.

- **Windows (Recommended)**:
  Run in PowerShell or Command Prompt:
  ```powershell
  winget install ffmpeg
  ```
  *(Restart terminal after installing so system PATH refreshes)*

- **macOS**:
  ```bash
  brew install ffmpeg
  ```

- **Linux (Ubuntu/Debian)**:
  ```bash
  sudo apt update && sudo apt install ffmpeg -y
  ```

---

## 🚀 Quick Start Instructions

### 1. Install Dependencies
In project root directory, run:
```bash
py -m pip install -r backend/requirements.txt
```

### 2. Launch the Application Server
Run Uvicorn server:
```bash
py -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Open in Browser
Open your browser and navigate to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 📂 Project Structure

```
.
├── backend/
│   ├── main.py            # FastAPI API server & yt-dlp conversion logic
│   └── requirements.txt   # Dependencies (fastapi, uvicorn, yt-dlp, pydantic)
├── frontend/
│   ├── index.html         # Modern web application UI
│   ├── style.css          # Glassmorphism dark mode design system
│   └── app.js             # Polling & UI interactive controller
├── downloads/             # Temporary converted files storage
└── README.md
```
