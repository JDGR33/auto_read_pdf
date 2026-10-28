import os
import re
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


def clean_text_with_rules(raw_text: str) -> str:
    """Fast, 100% offline rule-based cleaner for extracted PDF text.

    Strips page markers, running headers/footers, inline citations,
    and fixes line-break hyphenations and PDF kerning glitches.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Raw text cannot be empty.")

    lines = raw_text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue

        # 1. Remove our internal page boundary markers: --- [Page 20] ---
        if re.match(r"^---\s*\[Page\s+\d+\]\s*---$", stripped):
            continue

        # 2. Remove standalone page numbers (Arabic or Roman numerals)
        if re.match(r"^(\d+|[ivxlcdmIVXLCDM]+)$", stripped):
            continue

        # 3. Remove common book headers/footers with pipe separators:
        # e.g. "xiv | Preface", "Preface | xv", "24 | Chapter 1: ..."
        if re.match(r"^(\d+|[ivxlcdmIVXLCDM]+)\s*\|\s*.+$", stripped) or re.match(
            r"^.+\s*\|\s*(\d+|[ivxlcdmIVXLCDM]+)$", stripped
        ):
            continue

        # 4. Remove figure/table caption headers if they stand alone
        if re.match(r"^(Figure|Table)\s+\d+[-.]\d+\..*$", stripped):
            continue

        # 5. Fix trailing duplicate bullet artifacts (e.g. "• some text•")
        if stripped.startswith("•") and stripped.endswith("•") and len(stripped) > 2:
            stripped = stripped[:-1].rstrip()
        elif stripped.endswith("•") and not stripped.startswith("•"):
            stripped = stripped[:-1].rstrip()

        cleaned_lines.append(stripped)

    text = "\n".join(cleaned_lines)

    # 6. Fix hyphenated words split across line breaks (handles standard '-' and soft/Unicode '‐', '‑', '­')
    text = re.sub(r"([a-zA-Z])[-\u2010\u2011\u00ad]\s*\n\s*([a-zA-Z])", r"\1\2", text)

    # 7. Fix common PDF capital-letter kerning glitches (e.g. "Y ou" -> "You", "T o" -> "To", "W e" -> "We")
    text = re.sub(r"\bY\s+ou", "You", text)
    text = re.sub(r"\bT\s+o\b", "To", text)
    text = re.sub(r"\bW\s+e\b", "We", text)
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)

    # 8. Remove bracketed numeric citations like [1], [12, 15]
    text = re.sub(r"\s*\[\d+(?:\s*,\s*\d+)*\]", "", text)

    # 9. Unwrap single line breaks within paragraphs while keeping paragraph breaks (\n\n) and bullets
    paragraphs = re.split(r"\n\s*\n", text)
    merged_paragraphs = []
    for para in paragraphs:
        para_lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        if not para_lines:
            continue
        # Keep bullet lists on separate lines, otherwise join wrapped lines with spaces
        rebuilt = []
        for ln in para_lines:
            if ln.startswith(("•", "-", "*")) or not rebuilt:
                rebuilt.append(ln)
            else:
                rebuilt[-1] = f"{rebuilt[-1]} {ln}"
        merged_paragraphs.append("\n".join(rebuilt))

    return "\n\n".join(merged_paragraphs).strip()


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


def clean_text(raw_text: str, mode: str = "rules") -> str:
    """Clean raw PDF text using the chosen mode ('rules' or 'gemini')."""
    if mode == "rules":
        return clean_text_with_rules(raw_text)
    if mode == "gemini":
        return clean_text_with_llm(raw_text)
    raise ValueError(f"Unknown cleaning mode: {mode}")
