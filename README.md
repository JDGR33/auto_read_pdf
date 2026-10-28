# Auto Read PDF

A minimal, straightforward tool to convert a specific page range of a PDF file into a clean, natural-sounding voice recording.

## Design Philosophy
- **Simplicity First**: Avoid over-engineering. Keep the codebase flat, readable, and focused on core functions.
- **Step-by-Step Modularity**: Each stage (TTS, PDF Extraction, LLM Cleaning, UI) is a clean function/module that can be tested independently.

## Architecture & Workflow
```text
[PDF File + Page Range] 
       │
       ▼
1. PDF Parser (pypdf / PyMuPDF) -> Raw Text
       │
       ▼
2. LLM Cleaner (API)            -> Clean Text (no footnotes, page numbers, or figure captions)
       │
       ▼
3. Text-to-Speech (TTS)         -> Audio File (.mp3 / .wav)
```

## Implementation Roadmap

- [x] **Step 1: Text-to-Speech (TTS) Module (`tts.py`)**
  - Built [`text_to_speech`](file:///home/julio/auto_read_pdf/tts.py#L12-L33) using `edge-tts` (free, zero API keys needed, natural neural voices, adjustable speed).
- [ ] **Step 2: PDF Extraction & LLM Cleaning (`pdf_parser.py` & `cleaner.py`)**
  - Extract raw text from a given start/end page range using `pypdf`.
  - Pass page text through an LLM API (e.g., Gemini Flash or OpenAI GPT-4o-mini) with a strict system prompt to strip out page numbers, headers/footers, citations, footnotes, and image/table descriptions while keeping the main body text intact.
- [ ] **Step 3: CLI Pipeline (`main.py`)**
  - Tie the modules together: take a PDF path, start page, end page, and output filename from the command line.
- [ ] **Step 4: Simple UI (`app.py`)**
  - Add a lightweight single-file web UI (using **Streamlit** or **Gradio**) to upload a PDF, pick a page range, and play/download the generated audio directly in the browser.

## WSL & UI Notes
Running in **WSL (Windows Subsystem for Linux)** works smoothly with this setup:
- **Recommended UI (Web-based)**: Using **Streamlit** or **Gradio** starts a local web server inside WSL (`localhost:8501` or `localhost:7860`). WSL automatically forwards `localhost` to Windows, so you can open it in your regular Windows browser—where file drag-and-drop and HTML5 audio playback work out of the box without any WSL audio driver issues.
- **Desktop GUI (WSLg)**: Modern WSL2 supports native Linux GUI windows (like `tkinter`), though routing live audio directly from Linux to Windows speakers can occasionally be finicky compared to playing the generated `.mp3` in a Windows browser or Windows media player.
