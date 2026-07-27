---
title: YT Audio Extractor
emoji: 🎵
colorFrom: purple
colorTo: indigo
sdk: gradio
sdk_version: "4.44.0"
app_file: app.py
pinned: false
license: mit
---

# YT Audio Extractor 🎵

A studio-quality YouTube Audio Extractor web application built with **FastAPI**, **yt-dlp**, **FFmpeg**, and modern glassmorphism frontend.

## Key Features

- **320kbps Maximum Quality**: Extract YouTube audio streams at highest available bitrate and convert to 320kbps MP3.
- **Playlist Extraction**: Support for playlist URLs — extracts all tracks and packages into a `.zip` archive.
- **Real-Time Progress Tracking**: Live status messages, progress bar, transfer speed and ETA.
- **Built-in Audio Player Preview**: Listen to processed audio before downloading directly from the UI.
- **Automatic Disk Cleanup**: Downloads folder auto-purges files older than 1 hour.

## 🛠️ Local Setup

### 1. Install Dependencies
```bash
py -m pip install -r requirements.txt
```

### 2. Run the Server
```bash
py app.py
```

### 3. Open in Browser
👉 **[http://127.0.0.1:7860](http://127.0.0.1:7860)**

## 📂 Project Structure

```
.
├── backend/
│   ├── main.py            # FastAPI API server & yt-dlp conversion logic
│   └── requirements.txt   # Backend dependencies
├── frontend/
│   ├── index.html         # Modern glassmorphism UI
│   ├── style.css          # Dark mode design system
│   └── app.js             # Polling & UI interactive controller
├── downloads/             # Temporary converted files (auto-purged after 1hr)
├── app.py                 # Entry point
└── requirements.txt       # All dependencies
```
