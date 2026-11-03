"""Core media processing for the auto-censor CLI."""
from __future__ import annotations
import math, os, re, subprocess, tempfile
from pathlib import Path
from typing import Any, Iterable
from faster_whisper import WhisperModel
from pydub import AudioSegment

DEFAULT_WORDS = ("хуй хуя хуе хуи хули хуле пизд еба еби ебу ебн ебл ёб епт епан бля муда мудо говн гандон кондон пидор пидар педри сука сучк залуп шлюх простит").split()

def build_pattern(words: Iterable[str] = DEFAULT_WORDS) -> re.Pattern[str]:
    terms = sorted({w.strip().lower() for w in words if w and w.strip()}, key=len, reverse=True)
    return re.compile("(?:" + "|".join(re.escape(w) for w in terms) + ")", re.IGNORECASE) if terms else re.compile(r"(?!x)x")

PROFANITY_PATTERN = build_pattern()

def is_profanity(word: str, pattern: re.Pattern[str] = PROFANITY_PATTERN) -> bool:
    return bool(pattern.search(word.strip(".,!?-\"'()[]{} \n\t")))

def iter_profanity_words(result: dict[str, Any], pattern: re.Pattern[str] = PROFANITY_PATTERN) -> Iterable[dict[str, Any]]:
    for segment in result.get("segments", []):
        for word in segment.get("words", []) or []:
            if is_profanity(str(word.get("word", "")), pattern): yield word

def run_ffmpeg(command: list[str]) -> None:
    try: subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    except FileNotFoundError as exc: raise RuntimeError("FFmpeg не найден в PATH. Установите FFmpeg или используйте Docker.") from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or b"").decode(errors="replace").strip(); raise RuntimeError(f"FFmpeg завершился с ошибкой: {details[-800:]}") from exc

def extract_audio(source: Path, whisper_audio: Path, full_audio: Path) -> None:
    for output, channels, rate in ((whisper_audio, 1, 16000), (full_audio, 2, 44100)):
        run_ffmpeg(["ffmpeg", "-y", "-i", str(source), "-map", "0:a:0", "-vn", "-ac", str(channels), "-ar", str(rate), str(output)])

def censor_audio(audio_path: Path, result: dict[str, Any], *, pattern: re.Pattern[str] = PROFANITY_PATTERN, padding_type: str = "percent", padding_start: float = 20, padding_end: float = 20, volume_reduction: float = 0, fade_ms: int = 0) -> tuple[Path, int]:
    audio = AudioSegment.from_file(audio_path); volume_reduction = min(1.0, max(0.0, float(volume_reduction))); gain_db = -120.0 if volume_reduction == 0 else 20 * math.log10(volume_reduction)
    intervals: list[tuple[int, int]] = []
    for word in iter_profanity_words(result, pattern):
        try: start = max(0, int(float(word["start"]) * 1000)); end = min(len(audio), int(float(word["end"]) * 1000))
        except (KeyError, TypeError, ValueError): continue
        if end <= start: continue
        duration = end - start
        if padding_type == "percent": left, right = int(duration * max(0, padding_start) / 100), int(duration * max(0, padding_end) / 100)
        else: left, right = int(max(0, padding_start)), int(max(0, padding_end))
        cut_start, cut_end = start + left, end - right
        if cut_end <= cut_start: cut_start, cut_end = start, end
        intervals.append((cut_start, cut_end))
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], end)
        else: merged.append([start, end])
    for start, end in reversed(merged):
        muted = audio[start:end].apply_gain(gain_db)
        if fade_ms > 0:
            fade = min(fade_ms, max(1, (end - start) // 2)); muted = muted.fade_in(fade).fade_out(fade)
        audio = audio[:start] + muted + audio[end:]
    fd, name = tempfile.mkstemp(suffix="_censored.wav"); os.close(fd); Path(name).unlink(missing_ok=True); output = Path(name); audio.export(output, format="wav")
    return output, len(merged)

def merge_output(source: Path, audio: Path, output: Path, export_type: str, audio_format: str = "mp3") -> Path:
    audio_format = audio_format if audio_format in {"mp3", "wav", "flac", "m4a"} else "mp3"
    output = output.with_suffix("." + (audio_format if export_type == "audio_only" else "mp4")); output.parent.mkdir(parents=True, exist_ok=True)
    if export_type == "audio_only":
        codec = {"mp3": ["-c:a", "libmp3lame", "-b:a", "192k"], "wav": ["-c:a", "pcm_s16le"], "flac": ["-c:a", "flac"], "m4a": ["-c:a", "aac", "-b:a", "192k"]}.get(audio_format, ["-c:a", "libmp3lame", "-b:a", "192k"])
        command = ["ffmpeg", "-y", "-i", str(audio), *codec, str(output)]
    else: command = ["ffmpeg", "-y", "-i", str(source), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(output)]
    run_ffmpeg(command); return output

def process_media(input_path: Path, output_path: Path, model: WhisperModel, **options: Any) -> tuple[Path, int]:
    with tempfile.TemporaryDirectory(prefix="auto-censor-") as work:
        whisper_audio, full_audio = Path(work) / "whisper.wav", Path(work) / "full.wav"; extract_audio(input_path, whisper_audio, full_audio)
        segments, _ = model.transcribe(str(whisper_audio), language=options.get("language", "ru"), word_timestamps=True, vad_filter=True)
        result = {"segments": [{"words": [{"word": w.word, "start": w.start, "end": w.end} for w in (segment.words or [])]} for segment in segments]}
        censored, count = censor_audio(full_audio, result, pattern=options.get("pattern", PROFANITY_PATTERN), padding_type=options.get("padding_type", "percent"), padding_start=options.get("padding_start", 20), padding_end=options.get("padding_end", 20), volume_reduction=options.get("volume_reduction", 0), fade_ms=options.get("fade_ms", 0))
        try: return merge_output(input_path, censored, output_path, options.get("export_type", "video"), options.get("audio_format", "mp3")), count
        finally: censored.unlink(missing_ok=True)



