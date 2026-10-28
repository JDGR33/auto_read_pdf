import asyncio
import os
import re
import wave
import edge_tts
from edge_tts.exceptions import NoAudioReceived
import numpy as np
import soundfile as sf

DEFAULT_VOICE = "en-US-AndrewNeural"
PIPER_MODEL_PATH = "models/en_US-lessac-medium.onnx"
KOKORO_MODEL_PATH = "models/kokoro-v1.0.fp16.onnx"
KOKORO_FALLBACK_MODEL_PATH = "models/kokoro-v1.0.int8.onnx"
KOKORO_VOICES_PATH = "models/voices-v1.0.bin"

_PIPER_INSTANCE = globals().get("_PIPER_INSTANCE")
_KOKORO_INSTANCE = globals().get("_KOKORO_INSTANCE")


def _sanitize_for_tts(text: str) -> str:
    """Clean up characters or empty lines that can cause TTS issues."""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _split_into_chunks(text: str, max_chars: int = 1800) -> list[str]:
    """Split text into paragraph chunks so edge-tts can generate them in parallel."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks or [text]


async def _fetch_edge_chunk(chunk_text: str, voice: str, rate: str, sem: asyncio.Semaphore) -> bytes:
    async with sem:
        last_err = None
        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(text=chunk_text, voice=voice, rate=rate)
                audio_data = bytearray()
                async for msg in communicate.stream():
                    if msg["type"] == "audio":
                        audio_data.extend(msg["data"])
                if not audio_data:
                    raise NoAudioReceived("Empty audio stream")
                return bytes(audio_data)
            except Exception as err:
                last_err = err
                await asyncio.sleep(0.8 * (attempt + 1))
        raise RuntimeError(f"Edge TTS chunk failed after 3 attempts: {last_err}")


async def _generate_edge_parallel(text: str, output_path: str, voice: str, rate: str) -> None:
    chunks = _split_into_chunks(text, max_chars=1800)
    sem = asyncio.Semaphore(4)  # Up to 4 parallel streams
    parts = await asyncio.gather(*[_fetch_edge_chunk(c, voice, rate, sem) for c in chunks])
    with open(output_path, "wb") as f:
        for part in parts:
            f.write(part)


def _generate_piper(text: str, output_path: str) -> None:
    global _PIPER_INSTANCE
    from piper import PiperVoice

    if _PIPER_INSTANCE is None:
        if not os.path.exists(PIPER_MODEL_PATH):
            raise FileNotFoundError(f"Piper model not found at {PIPER_MODEL_PATH}")
        _PIPER_INSTANCE = PiperVoice.load(PIPER_MODEL_PATH)

    with wave.open(output_path, "wb") as wav_file:
        _PIPER_INSTANCE.synthesize_wav(text, wav_file)


def _generate_kokoro(text: str, output_path: str, voice: str = "af_heart") -> None:
    global _KOKORO_INSTANCE
    import onnxruntime as ort
    from kokoro_onnx import Kokoro

    if _KOKORO_INSTANCE is None:
        model_path = (
            KOKORO_MODEL_PATH
            if os.path.exists(KOKORO_MODEL_PATH)
            else KOKORO_FALLBACK_MODEL_PATH
        )
        if not os.path.exists(model_path) or not os.path.exists(KOKORO_VOICES_PATH):
            raise FileNotFoundError("Kokoro model files not found in models/ directory.")
        if hasattr(ort, "preload_dlls"):
            try:
                ort.preload_dlls(directory="")
            except Exception:
                pass
        sess_options = ort.SessionOptions()
        sess_options.log_severity_level = 3
        available = ort.get_available_providers()
        providers = [
            p for p in ("CUDAExecutionProvider", "CPUExecutionProvider") if p in available
        ] or ["CPUExecutionProvider"]
        session = ort.InferenceSession(model_path, sess_options=sess_options, providers=providers)
        _KOKORO_INSTANCE = Kokoro.from_session(session, KOKORO_VOICES_PATH)

    samples, sample_rate = _KOKORO_INSTANCE.create(
        text, voice=voice, speed=1.0, lang="en-us"
    )
    sf.write(output_path, samples, sample_rate)


def text_to_speech(
    text: str,
    output_path: str = "output.mp3",
    voice: str = DEFAULT_VOICE,
    rate: str = "+0%",
    engine: str = "edge",
) -> str:
    """Convert text to an audio file using the chosen TTS engine ('edge', 'piper', or 'kokoro').

    Args:
        text: The text string to convert into speech.
        output_path: Path where the audio file will be saved.
        voice: Voice identifier (used by edge/kokoro).
        rate: Speech speed adjustment for edge-tts.
        engine: 'edge' (Cloud parallel MP3), 'piper' (Fast local WAV), or 'kokoro' (Expressive local WAV).

    Returns:
        The path to the saved audio file.
    """
    cleaned_text = _sanitize_for_tts(text or "")
    if not cleaned_text or not any(ch.isalnum() for ch in cleaned_text):
        raise ValueError(
            "No speakable text remained on the selected page(s) (page may be blank or only contain images/headers)."
        )

    if engine == "piper":
        if output_path.endswith(".mp3"):
            output_path = output_path[:-4] + "_piper.wav"
        _generate_piper(cleaned_text, output_path)
    elif engine == "kokoro":
        if output_path.endswith(".mp3"):
            output_path = output_path[:-4] + "_kokoro.wav"
        kokoro_voice = voice if voice in ("af_heart", "am_adam", "af_bella", "bm_george") else "af_heart"
        _generate_kokoro(cleaned_text, output_path, voice=kokoro_voice)
    else:
        asyncio.run(_generate_edge_parallel(cleaned_text, output_path, voice, rate))

    return output_path
