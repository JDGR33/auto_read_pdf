import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

SYSTEM_PROMPT = """You are a text cleaning assistant preparing extracted PDF book pages for Text-to-Speech (TTS) audio narration.

Your ONLY job is to output the clean, readable main body text verbatim while removing non-narrative PDF artifacts:
1. REMOVE page numbers, running headers, and running footers (including markers like '--- [Page X] ---' or 'xiv | Preface').
2. REMOVE footnotes, endnotes, inline citation markers (like [1], [2], or superscript numbers), and bibliography/reference lists.
3. REMOVE figure captions, image descriptions, table data, and code block line numbers that do not flow as natural speech.
4. FIX broken words caused by line-break hyphenation (e.g. 'engi-neering' -> 'engineering') and OCR/kerning spaces (e.g. 'Y ou' -> 'You'), and merge sentences that were split across page breaks.
5. DO NOT summarize, paraphrase, rewrite, or add commentary. Keep the author's exact words and paragraphs for the main text.
6. Return ONLY the cleaned text ready to be spoken aloud."""

DEFAULT_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
]


def get_api_key() -> str:
    """Retrieve the Gemini API key from environment variables."""
    api_key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GEMINNI_API")
        or os.getenv("GEMINNI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )
    if not api_key:
        raise ValueError(
            "Gemini API key not found. Please set GEMINI_API_KEY or GEMINNI_API in your .env file."
        )
    return api_key.strip()


def clean_text_with_llm(raw_text: str, model: str | None = None) -> str:
    """Clean extracted PDF text using Gemini to remove junk for TTS narration.

    Args:
        raw_text: The raw text extracted from the PDF.
        model: Optional specific Gemini model name to use.

    Returns:
        Cleaned text suitable for text-to-speech.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Raw text cannot be empty.")

    client = genai.Client(api_key=get_api_key())
    models_to_try = [model] if model else DEFAULT_MODELS

    last_error = None
    for candidate_model in models_to_try:
        try:
            response = client.models.generate_content(
                model=candidate_model,
                contents=raw_text,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.0,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            if response.text and response.text.strip():
                return response.text.strip()
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(f"Failed to clean text with Gemini: {last_error}")
