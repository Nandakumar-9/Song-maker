import os
import sys

# Ensure current working directory is at the top of sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import uvicorn
import gradio as gr
from backend.main import app as fastapi_app

# HuggingFace Spaces requires a Gradio app.
# We mount a minimal hidden Gradio block into the FastAPI app.
# The real UI is served by FastAPI at "/" (custom HTML/CSS/JS frontend).
with gr.Blocks(title="YT Audio Extractor") as demo:
    gr.HTML("<p style='display:none'>YT Audio Extractor Backend</p>")

# Mount Gradio at /gradio so HuggingFace is satisfied
app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
