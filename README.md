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
1. PDF Parser (pypdf)           -> Raw Text
       │
       ▼
2. LLM Cleaner (Gemini API)     -> Clean Text (no footnotes, page numbers, or figure captions)
       │
       ▼
3. Text-to-Speech (edge-tts)    -> Audio File (.mp3)
```

## Quick Start

### 1. Environment Setup
Make sure your `.env` file has your Gemini API key:
```env
GEMINI_API_KEY=your_api_key_here
```

### 2. Run the Web UI (Recommended)
```bash
.venv/bin/streamlit run app.py
```
Then open `http://localhost:8501` in your browser. From the UI you can:
1. Select a PDF from the `library/` folder or upload one.
2. Pick the **Start Page**, **End Page**, and **Reading Speed**.
3. Click **Generate & Play Audio** and use the built-in player controls (play, pause, seek, playback speed, or download).

### 3. Run via CLI
```bash
.venv/bin/python main.py "library/your_book.pdf" --start 20 --end 21 --output chapter1.mp3
```

## Implementation Roadmap

- [x] **Step 1: Text-to-Speech (TTS) Module (`tts.py`)**
  - Built [`text_to_speech`](file:///home/julio/auto_read_pdf/tts.py#L12-L33) using `edge-tts` (free, zero API keys needed, natural neural voices, adjustable speed).
- [x] **Step 2: PDF Extraction & LLM Cleaning (`pdf_parser.py` & `cleaner.py`)**
  - Built [`extract_text_from_pdf`](file:///home/julio/auto_read_pdf/pdf_parser.py#L4-L28) using `pypdf` to extract raw text from a 1-based inclusive page range.
  - Built [`clean_text_with_llm`](file:///home/julio/auto_read_pdf/cleaner.py#L40-L71) using the Google Gemini API (`google-genai`) to strip out page numbers, headers/footers, footnotes, and broken hyphenations while keeping the main body text verbatim.
- [x] **Step 3: CLI Pipeline (`main.py`)**
  - Built [`pdf_to_audio`](file:///home/julio/auto_read_pdf/main.py#L7-L30) to tie PDF extraction, LLM cleaning, and TTS generation together.
- [x] **Step 4: Simple UI (`app.py`)**
  - Built a lightweight Streamlit web UI ([`app.py`](file:///home/julio/auto_read_pdf/app.py)) to pick a PDF (from `library/` or via file upload), set the page range, and play/pause the generated `.mp3` directly in the browser.
