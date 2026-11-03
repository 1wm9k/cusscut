from processor import build_pattern, is_profanity, censor_audio, process_media
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
    assert is_profanity("ЁБ")
    assert not is_profanity("художник")


def test_dictionary_match_modes():
    assert is_profanity("материал", build_pattern(["мат"], "substring"))
    assert is_profanity("материться", build_pattern(["мат"], "prefix"))
    assert not is_profanity("помат", build_pattern(["мат"], "prefix"))
    assert is_profanity("мат", build_pattern(["мат"], "exact"))
    assert not is_profanity("материться", build_pattern(["мат"], "exact"))

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


def test_censor_audio_without_matches_copies_source(tmp_path: Path):
    source = tmp_path / "source.wav"
    write_silence(source, 1000)

    output, count = censor_audio(source, {"segments": [{"words": [{"word": "обычное", "start": 0, "end": 1}]}]})
    try:
        assert count == 0
        assert output.read_bytes() == source.read_bytes()
    finally:
        output.unlink(missing_ok=True)


def test_min_probability_can_skip_word(tmp_path: Path):
    source = tmp_path / "source.wav"
    write_silence(source, 1000)
    result = {"segments": [{"words": [{"word": "бля", "start": 0.2, "end": 0.4, "probability": 0.2}]}]}

    output, count = censor_audio(source, result, min_probability=0.5)
    try:
        assert count == 0
    finally:
        output.unlink(missing_ok=True)


def test_transcription_cache_reuses_model_result(tmp_path: Path):
    class Word:
        word = "бля"
        start = 0.2
        end = 0.4
        probability = 0.9

    class Segment:
        words = [Word()]

    class FakeModel:
        calls = 0

        def transcribe(self, *_args, **_kwargs):
            self.calls += 1
            return iter([Segment()]), None

    source = tmp_path / "source.wav"
    write_silence(source, 1000)
    cache = tmp_path / "cache"
    model = FakeModel()
    options = {"export_type": "audio_only", "audio_format": "wav", "model_name": "test", "cache_dir": cache}
    process_media(source, tmp_path / "one.wav", model, **options)
    process_media(source, tmp_path / "two.wav", model, **options)

    assert model.calls == 1

