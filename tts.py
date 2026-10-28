import asyncio
import re
import edge_tts
from edge_tts.exceptions import NoAudioReceived

DEFAULT_VOICE = "en-US-AndrewNeural"


def _sanitize_for_tts(text: str) -> str:
    """Clean up characters or empty lines that can cause edge-tts NoAudioReceived."""
    # Remove control characters except newlines and tabs
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse excessive newlines/whitespace
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


async def _generate_audio(text: str, output_path: str, voice: str, rate: str) -> None:
    last_err = None
    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
            await communicate.save(output_path)
            return
        except NoAudioReceived as err:
            last_err = err
            await asyncio.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"TTS failed after 3 attempts: {last_err}")


def text_to_speech(
    text: str,
    output_path: str = "output.mp3",
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
) -> str:
    """Convert text to an MP3 audio file using edge-tts.

    Args:
        text: The text string to convert into speech.
        output_path: Path where the MP3 file will be saved.
        voice: Edge TTS voice name (e.g., 'en-US-AndrewNeural', 'en-US-AriaNeural').
        rate: Speech speed adjustment (e.g., '+0%', '+25%', '-10%').

    Returns:
        The path to the saved audio file.
    """
    cleaned_text = _sanitize_for_tts(text or "")
    if not cleaned_text or not any(ch.isalnum() for ch in cleaned_text):
        raise ValueError(
            "No speakable text remained on the selected page(s) (page may be blank or only contain images/headers)."
        )

    asyncio.run(_generate_audio(cleaned_text, output_path, voice, rate))
    return output_path
