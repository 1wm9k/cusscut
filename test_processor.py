from processor import is_profanity, censor_audio
from pathlib import Path
import wave


def write_silence(path: Path, duration_ms: int) -> None:
    frames = int(16000 * duration_ms / 1000)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\0\0" * frames)

def test_profanity_matching():
    assert is_profanity("бля")
    assert is_profanity("хуй!")
    assert not is_profanity("художник")

def test_censor_audio_handles_overlap_and_bounds(tmp_path: Path):
    source = tmp_path / "source.wav"
    write_silence(source, 1000)
    result = {"segments": [{"words": [
        {"word": "бля", "start": -1, "end": 0.4},
        {"word": "сука", "start": 0.15, "end": 0.8},
        {"word": "ok", "start": 0.8, "end": 0.9},
    ]}]}
    output, count = censor_audio(source, result, padding_type="percent", padding_start=20, padding_end=20)
    try:
        assert count == 1
        with wave.open(str(output), "rb") as handle:
            assert round(handle.getnframes() / handle.getframerate() * 1000) == 1000
    finally:
        output.unlink(missing_ok=True)

