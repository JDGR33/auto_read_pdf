import asyncio
import edge_tts

DEFAULT_VOICE = "en-US-AndrewNeural"


async def _generate_audio(text: str, output_path: str, voice: str, rate: str) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicate.save(output_path)


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
    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    asyncio.run(_generate_audio(text, output_path, voice, rate))
    return output_path


if __name__ == "__main__":
    sample_text = (
        "Hello! This is a test of the Auto Read PDF text to speech module. "
        "Step one is now working."
    )
    output_file = "test_output.mp3"
    print(f"Generating audio to '{output_file}'...")
    text_to_speech(sample_text, output_file, rate="+10%")
    print(f"Done! Saved to {output_file}")
