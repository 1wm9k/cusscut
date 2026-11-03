from processor import is_profanity, censor_audio
from pydub import AudioSegment
from pathlib import Path

def test_profanity_matching():
    assert is_profanity("бля")
    assert is_profanity("хуй!")
    assert not is_profanity("художник")

def test_censor_audio_handles_overlap_and_bounds(tmp_path: Path):
    source = tmp_path / "source.wav"
    AudioSegment.silent(duration=1000).export(source, format="wav")
    result = {"segments": [{"words": [
        {"word": "бля", "start": -1, "end": 0.4},
        {"word": "сука", "start": 0.15, "end": 0.8},
        {"word": "ok", "start": 0.8, "end": 0.9},
    ]}]}
    output, count = censor_audio(source, result, padding_type="percent", padding_start=20, padding_end=20)
    try:
        assert count == 1
        assert len(AudioSegment.from_file(output)) == 1000
    finally:
        output.unlink(missing_ok=True)

