import base64
import glob
import importlib
import os
import tempfile
import time
import streamlit as st
import streamlit.components.v1 as components
from pypdf import PdfReader
import cleaner
import db
import pdf_parser
import tts

from cleaner import clean_text
from db import (
    build_recording_path,
    get_cached_recording,
    init_db,
    list_recordings,
    save_recording,
)
from pdf_parser import extract_text_from_pdf
from tts import text_to_speech

init_db()

st.set_page_config(page_title="Auto Read PDF", page_icon="🎧", layout="centered")
st.title("🎧 Auto Read PDF")
st.caption("Select a PDF, choose a page range, and listen with live speed control.")

# 1. File Selection (from library/ folder or upload)
library_files = sorted(glob.glob("library/*.pdf"))
source_mode = st.radio(
    "PDF Source",
    options=["Select from library/ folder", "Upload a PDF file"],
    horizontal=True,
    index=0 if library_files else 1,
)

pdf_path = None
pdf_name = None

if source_mode == "Select from library/ folder":
    if library_files:
        pdf_path = st.selectbox(
            "Choose a PDF from library/",
            options=library_files,
            format_func=lambda p: os.path.basename(p),
        )
        pdf_name = os.path.basename(pdf_path)
    else:
        st.info("No PDF files found in the `library/` folder. Switch to 'Upload a PDF file'.")
else:
    uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])
    if uploaded_file is not None:
        pdf_name = uploaded_file.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getbuffer())
            pdf_path = tmp.name

# 2. Page Range, Cleaning Mode, TTS Engine & Audio Generation
if pdf_path and pdf_name:
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    st.caption(f"📄 Total pages in PDF: **{total_pages}**")

    col1, col2 = st.columns(2)
    with col1:
        start_page = int(
            st.number_input("Start Page", min_value=1, max_value=total_pages, value=20, step=1)
        )
    with col2:
        end_page = int(
            st.number_input(
                "End Page",
                min_value=start_page,
                max_value=total_pages,
                value=min(start_page, total_pages),
                step=1,
            )
        )

    opt_col1, opt_col2 = st.columns(2)
    with opt_col1:
        cleaner_choice = st.radio(
            "1. Text Cleaning Method",
            options=[
                "⚡ Fast Local Rules (Instant)",
                "✨ Gemini API (Cloud LLM)",
            ],
            index=0,
        )
        clean_mode = "rules" if cleaner_choice.startswith("⚡") else "gemini"

    with opt_col2:
        tts_choice = st.radio(
            "2. Voice Engine (TTS)",
            options=[
                "🚀 Piper (Local Offline - Fastest)",
                "🎭 Kokoro-82M (Local GPU - Expressive)",
                "☁️ Edge TTS (Cloud Parallel)",
            ],
            index=0,
        )
        if tts_choice.startswith("🚀"):
            tts_engine = "piper"
        elif tts_choice.startswith("🎭"):
            tts_engine = "kokoro"
        else:
            tts_engine = "edge"

    # Check if this exact page range is already cached in SQLite
    cached = get_cached_recording(pdf_name, start_page, end_page)
    if cached:
        cached_engine = (cached.get("tts_engine") or "edge").upper()
        cached_dur = cached.get("duration_sec") or 0.0
        dur_str = f" — generated in **{cached_dur:.2f}s**" if cached_dur else ""
        st.success(
            f"✅ Pages {start_page}–{end_page} already recorded ({cached_engine}{dur_str})!"
        )

    btn_col1, btn_col2 = st.columns([3, 1])
    with btn_col1:
        btn_label = (
            f"▶️ Play Cached Audio (Pages {start_page}–{end_page})"
            if cached
            else f"🔊 Generate & Play Audio (Pages {start_page}–{end_page})"
        )
        main_clicked = st.button(btn_label, type="primary", use_container_width=True)
    with btn_col2:
        regen_clicked = st.button(
            "🔄 Re-generate",
            disabled=not cached,
            help="Force re-cleaning and re-recording this page range with the selected options",
            use_container_width=True,
        )

    if main_clicked or regen_clicked:
        if cached and not regen_clicked:
            with open(cached["audio_path"], "rb") as f:
                st.session_state["audio_bytes"] = f.read()
            st.session_state["cleaned_text"] = cached["cleaned_text"]
            st.session_state["last_range"] = f"Pages {start_page}–{end_page} (Cached)"
            st.session_state["audio_path"] = cached["audio_path"]
            st.session_state["timing_summary"] = (
                f"⚡ Loaded from SQLite cache in 0.00s (Originally generated with {(cached.get('tts_engine') or 'edge').upper()} in {cached.get('duration_sec') or 0:.2f}s)"
            )
        else:
            total_start = time.perf_counter()
            status = st.status(f"⏱️ Processing pages {start_page}–{end_page}...", expanded=True)
            try:
                # Step 1: Extract PDF
                t0 = time.perf_counter()
                status.write("1/3 📄 Extracting raw text from PDF...")
                raw_text = extract_text_from_pdf(pdf_path, start_page, end_page)
                if not raw_text.strip():
                    raise ValueError(f"No readable text found on pages {start_page}–{end_page}.")
                t_extract = time.perf_counter() - t0
                status.write(f"   ✓ Extracted {len(raw_text):,} chars in **{t_extract:.2f}s**")

                # Step 2: Clean Text
                t1 = time.perf_counter()
                status.write(f"2/3 ✨ Cleaning text using **{clean_mode.upper()}**...")
                cleaned_text = clean_text(raw_text, mode=clean_mode)
                t_clean = time.perf_counter() - t1
                status.write(f"   ✓ Cleaned text ({len(cleaned_text):,} chars) in **{t_clean:.2f}s**")

                # Step 3: TTS Audio Synthesis
                t2 = time.perf_counter()
                status.write(f"3/3 🎙️ Generating speech using **{tts_engine.upper()}**...")
                output_file = build_recording_path(pdf_name, start_page, end_page, tts_engine=tts_engine)
                audio_file = text_to_speech(
                    text=cleaned_text, output_path=output_file, engine=tts_engine
                )
                t_tts = time.perf_counter() - t2
                total_elapsed = time.perf_counter() - total_start
                status.write(f"   ✓ Audio synthesized in **{t_tts:.2f}s**")

                save_recording(
                    pdf_name,
                    start_page,
                    end_page,
                    audio_file,
                    cleaned_text,
                    tts_engine=tts_engine,
                    duration_sec=total_elapsed,
                )

                with open(audio_file, "rb") as f:
                    st.session_state["audio_bytes"] = f.read()
                st.session_state["cleaned_text"] = cleaned_text
                st.session_state["last_range"] = (
                    f"Pages {start_page}–{end_page} ({tts_engine.upper()})"
                )
                st.session_state["audio_path"] = audio_file
                st.session_state["timing_summary"] = (
                    f"⏱️ **Total Time: {total_elapsed:.2f}s** — "
                    f"PDF Extract: `{t_extract:.2f}s` | "
                    f"Clean ({clean_mode}): `{t_clean:.2f}s` | "
                    f"TTS ({tts_engine}): `{t_tts:.2f}s`"
                )
                status.update(
                    label=f"✅ Completed in {total_elapsed:.2f}s! (TTS: {t_tts:.2f}s)",
                    state="complete",
                    expanded=False,
                )
            except Exception as exc:
                status.update(label="Generation failed", state="error", expanded=True)
                st.error(f"Error: {exc}")

    # Show previously recorded page ranges for this PDF
    saved_list = list_recordings(pdf_name)
    if saved_list:
        with st.expander(f"🗂️ Saved Recordings for this Book ({len(saved_list)})"):
            for item in saved_list:
                r_col1, r_col2, r_col3 = st.columns([3, 3, 2])
                eng_badge = (item.get("tts_engine") or "edge").upper()
                dur_badge = f"{item.get('duration_sec') or 0:.1f}s"
                r_col1.write(f"**Pages {item['start_page']}–{item['end_page']}** (`{eng_badge}`, {dur_badge})")
                r_col2.caption(f"`{os.path.basename(item['audio_path'])}`")
                if r_col3.button(
                    "▶️ Load",
                    key=f"load_{item['id']}",
                    use_container_width=True,
                ):
                    with open(item["audio_path"], "rb") as f:
                        st.session_state["audio_bytes"] = f.read()
                    st.session_state["cleaned_text"] = item["cleaned_text"]
                    st.session_state["last_range"] = (
                        f"Pages {item['start_page']}–{item['end_page']} ({eng_badge})"
                    )
                    st.session_state["audio_path"] = item["audio_path"]
                    st.session_state["timing_summary"] = (
                        f"⏱️ Originally generated with **{eng_badge}** in **{dur_badge}**"
                    )

# 3. Audio Player with Live Dynamic Speed Control & Timer Summary
if "audio_bytes" in st.session_state:
    st.divider()
    st.subheader(f"▶️ Audio Player ({st.session_state.get('last_range', '')})")
    if "timing_summary" in st.session_state:
        st.info(st.session_state["timing_summary"])
    if "audio_path" in st.session_state:
        st.caption(f"File: `{st.session_state['audio_path']}`")

    audio_ext = "wav" if st.session_state.get("audio_path", "").endswith(".wav") else "mp3"
    b64_audio = base64.b64encode(st.session_state["audio_bytes"]).decode("utf-8")
    player_html = f"""
    <div style="font-family: sans-serif; background: #1e1e2e; color: #ffffff; padding: 16px; border-radius: 10px;">
        <audio id="pdfAudio" controls style="width: 100%; margin-bottom: 12px;" src="data:audio/{audio_ext};base64,{b64_audio}"></audio>
        <div style="display: flex; align-items: center; gap: 12px; font-size: 14px;">
            <label for="speedSlider" style="font-weight: 600; min-width: 145px;">⚡ Live Speed: <span id="speedVal">1.00x</span></label>
            <input id="speedSlider" type="range" min="0.5" max="2.5" step="0.05" value="1.0" style="flex: 1; cursor: pointer;">
            <button onclick="setSpeed(1.0)" style="padding: 4px 8px; border-radius: 4px; border: 1px solid #555; background: #333; color: #fff; cursor: pointer;">1x</button>
            <button onclick="setSpeed(1.25)" style="padding: 4px 8px; border-radius: 4px; border: 1px solid #555; background: #333; color: #fff; cursor: pointer;">1.25x</button>
            <button onclick="setSpeed(1.5)" style="padding: 4px 8px; border-radius: 4px; border: 1px solid #555; background: #333; color: #fff; cursor: pointer;">1.5x</button>
            <button onclick="setSpeed(2.0)" style="padding: 4px 8px; border-radius: 4px; border: 1px solid #555; background: #333; color: #fff; cursor: pointer;">2x</button>
        </div>
    </div>
    <script>
        const audio = document.getElementById('pdfAudio');
        const slider = document.getElementById('speedSlider');
        const label = document.getElementById('speedVal');
        function setSpeed(val) {{
            audio.playbackRate = val;
            slider.value = val;
            label.textContent = Number(val).toFixed(2) + 'x';
        }}
        slider.addEventListener('input', (e) => setSpeed(e.target.value));
    </script>
    """
    components.html(player_html, height=130)

    with st.expander("📖 View Cleaned Text"):
        st.write(st.session_state.get("cleaned_text", ""))
