import argparse
import os
from cleaner import clean_text_with_llm
from db import build_recording_path, get_cached_recording, save_recording
from pdf_parser import extract_text_from_pdf
from tts import DEFAULT_VOICE, text_to_speech


def pdf_to_audio(
    pdf_path: str,
    start_page: int,
    end_page: int,
    output_path: str | None = None,
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
    pdf_name: str | None = None,
    force_regenerate: bool = False,
) -> tuple[str, str, bool]:
    """Full pipeline with SQLite caching: check DB first, otherwise extract, clean, TTS, and save.

    Returns:
        Tuple of (output_audio_path, cleaned_text, from_cache).
    """
    book_name = pdf_name or os.path.basename(pdf_path)

    if not force_regenerate:
        cached = get_cached_recording(book_name, start_page, end_page)
        if cached:
            return cached["audio_path"], cached["cleaned_text"], True

    raw_text = extract_text_from_pdf(pdf_path, start_page, end_page)
    if not raw_text.strip():
        raise ValueError(f"No readable text found on pages {start_page}-{end_page}.")

    cleaned_text = clean_text_with_llm(raw_text)
    target_path = output_path or build_recording_path(book_name, start_page, end_page)
    audio_path = text_to_speech(
        text=cleaned_text,
        output_path=target_path,
        voice=voice,
        rate=rate,
    )
    save_recording(book_name, start_page, end_page, audio_path, cleaned_text)
    return audio_path, cleaned_text, False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert PDF pages to clean speech.")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--start", type=int, required=True, help="Start page (1-based)")
    parser.add_argument("--end", type=int, required=True, help="End page (1-based)")
    parser.add_argument("--output", default=None, help="Optional custom output MP3 path")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Edge TTS voice name")
    parser.add_argument("--rate", default="+0%", help="Speech rate (e.g. '+20%%')")
    parser.add_argument("--force", action="store_true", help="Ignore SQLite cache and regenerate")

    args = parser.parse_args()
    print(f"Processing '{args.pdf_path}' (pages {args.start} to {args.end})...")
    out_file, _, is_cached = pdf_to_audio(
        pdf_path=args.pdf_path,
        start_page=args.start,
        end_page=args.end,
        output_path=args.output,
        voice=args.voice,
        rate=args.rate,
        force_regenerate=args.force,
    )
    status_msg = "Loaded from SQLite cache" if is_cached else "Generated and saved"
    print(f"Done! ({status_msg}) Audio path: {out_file}")
