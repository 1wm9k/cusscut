"""Core media processing for the auto-censor CLI."""
from __future__ import annotations
import hashlib, json, os, re, subprocess, tempfile
import shutil
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from faster_whisper import WhisperModel

DEFAULT_WORDS = ("хуй хуя хуе хуи хули хуле пизд еба еби ебу ебн ебл ёб епт епан бля муда мудо говн гандон кондон пидор пидар педри сука сучк залуп шлюх простит").split()

def normalize_word(value: str) -> str:
    return unicodedata.normalize("NFKC", value).lower().replace("ё", "е")

def build_pattern(words: Iterable[str] = DEFAULT_WORDS, match_mode: str = "substring") -> re.Pattern[str]:
    if match_mode not in {"substring", "prefix", "exact"}:
        raise ValueError(f"Неизвестный режим сопоставления: {match_mode}")
    terms = sorted({normalize_word(w.strip()) for w in words if w and w.strip()}, key=len, reverse=True)
    if not terms:
        return re.compile(r"(?!x)x")
    body = "(?:" + "|".join(re.escape(w) for w in terms) + ")"
    if match_mode == "prefix": body = "^" + body
    if match_mode == "exact": body = "^" + body + "$"
    return re.compile(body, re.IGNORECASE)

PROFANITY_PATTERN = build_pattern()

def is_profanity(word: str, pattern: re.Pattern[str] = PROFANITY_PATTERN) -> bool:
    normalized = normalize_word(word.strip(".,!?-\"'()[]{} \n\t"))
    return bool(pattern.search(normalized))

def iter_profanity_words(result: dict[str, Any], pattern: re.Pattern[str] = PROFANITY_PATTERN, min_probability: float | None = None) -> Iterable[dict[str, Any]]:
    for segment in result.get("segments", []):
        for word in segment.get("words", []) or []:
            probability = word.get("probability")
            if min_probability is not None and probability is not None:
                try:
                    if float(probability) < min_probability:
                        continue
                except (TypeError, ValueError):
                    continue
            if is_profanity(str(word.get("word", "")), pattern): yield word

def run_ffmpeg(command: list[str]) -> None:
    try: subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    except FileNotFoundError as exc: raise RuntimeError("FFmpeg не найден в PATH. Установите FFmpeg или используйте Docker.") from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or b"").decode(errors="replace").strip(); raise RuntimeError(f"FFmpeg завершился с ошибкой: {details[-800:]}") from exc

def _audio_stream_count(source: Path) -> int:
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(source)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return 1
    return sum(1 for line in probe.stdout.splitlines() if line.strip())

def extract_audio(source: Path, whisper_audio: Path, full_audio: Path) -> None:
    for output, channels, rate in ((whisper_audio, 1, 16000), (full_audio, 2, 44100)):
        run_ffmpeg(["ffmpeg", "-y", "-i", str(source), "-map", "0:a:0", "-vn", "-ac", str(channels), "-ar", str(rate), str(output)])

def extract_full_audio(source: Path, full_audio: Path) -> None:
    run_ffmpeg(["ffmpeg", "-y", "-i", str(source), "-map", "0:a:0", "-vn", "-ac", "2", "-ar", "44100", str(full_audio)])

def _transcription_cache_path(source: Path, cache_dir: Path) -> Path:
    digest = hashlib.sha256(str(source.resolve()).encode("utf-8")).hexdigest()[:24]
    return cache_dir / f"{digest}.json"

def _transcription_cache_key(source: Path, model_name: str, language: str) -> str:
    stat = source.stat()
    payload = f"{source.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|{model_name}|{language}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _load_transcription_cache(source: Path, cache_dir: Path | None, model_name: str, language: str) -> dict[str, Any] | None:
    if cache_dir is None:
        return None
    try:
        payload = json.loads(_transcription_cache_path(source, cache_dir).read_text(encoding="utf-8"))
        if payload.get("key") == _transcription_cache_key(source, model_name, language):
            return payload["result"]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return None

def _save_transcription_cache(source: Path, cache_dir: Path | None, model_name: str, language: str, result: dict[str, Any]) -> None:
    if cache_dir is None:
        return
    temporary: Path | None = None
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = _transcription_cache_path(source, cache_dir)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps({"key": _transcription_cache_key(source, model_name, language), "result": result}, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

def _ffmpeg_volume_filter(intervals: list[tuple[int, int]], gain: float, fade_ms: int) -> str:
    filters: list[str] = []
    gain_text = f"{gain:.9f}"
    for start_ms, end_ms in intervals:
        start = start_ms / 1000
        end = end_ms / 1000
        fade = min(fade_ms / 1000, max(0.001, (end - start) / 2)) if fade_ms > 0 else 0
        if fade:
            left = start + fade
            right = end - fade
            expression = (
                f"if(lt(t,{left:.9f}),1-(1-{gain_text})*(t-{start:.9f})/{fade:.9f},"
                f"if(gt(t,{right:.9f}),{gain_text}+(1-{gain_text})*(t-{right:.9f})/{fade:.9f},{gain_text}))"
            )
        else:
            expression = gain_text
        filters.append(
            f"volume=volume='{expression}':eval=frame:enable='between(t,{start:.9f},{end:.9f})'"
        )
    return ",".join(filters)

def censor_audio(audio_path: Path, result: dict[str, Any], *, pattern: re.Pattern[str] = PROFANITY_PATTERN, min_probability: float | None = None, padding_type: str = "percent", padding_start: float = 20, padding_end: float = 20, volume_reduction: float = 0, fade_ms: int = 0) -> tuple[Path, int]:
    volume_reduction = min(1.0, max(0.0, float(volume_reduction)))
    intervals: list[tuple[int, int]] = []
    for word in iter_profanity_words(result, pattern, min_probability):
        try: start = max(0, int(float(word["start"]) * 1000)); end = int(float(word["end"]) * 1000)
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
    fd, name = tempfile.mkstemp(suffix="_censored.wav"); os.close(fd); Path(name).unlink(missing_ok=True); output = Path(name)
    if merged:
        gain = volume_reduction
        fd, script_name = tempfile.mkstemp(suffix=".ffscript"); os.close(fd); script = Path(script_name)
        try:
            script.write_text(f"[0:a]{_ffmpeg_volume_filter(merged, gain, fade_ms)}[aout]\n", encoding="utf-8")
            run_ffmpeg(["ffmpeg", "-y", "-i", str(audio_path), "-filter_complex_script", str(script), "-map", "[aout]", "-c:a", "pcm_s16le", str(output)])
        finally:
            script.unlink(missing_ok=True)
    else:
        shutil.copy2(audio_path, output)
    return output, len(merged)

def merge_output(source: Path, audio: Path, output: Path, export_type: str, audio_format: str = "mp3") -> Path:
    audio_format = audio_format if audio_format in {"mp3", "wav", "flac", "m4a"} else "mp3"
    output = output.with_suffix("." + (audio_format if export_type == "audio_only" else "mp4")); output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{output.stem}-", suffix=output.suffix, dir=output.parent)
    os.close(fd)
    temporary_output = Path(temporary_name)
    if export_type == "audio_only":
        codec = {"mp3": ["-c:a", "libmp3lame", "-b:a", "192k"], "wav": ["-c:a", "pcm_s16le"], "flac": ["-c:a", "flac"], "m4a": ["-c:a", "aac", "-b:a", "192k"]}.get(audio_format, ["-c:a", "libmp3lame", "-b:a", "192k"])
        command = ["ffmpeg", "-y", "-i", str(audio), *codec, str(temporary_output)]
    else:
        command = [
            "ffmpeg", "-y", "-i", str(source), "-i", str(audio),
            "-map", "0:v:0", "-map", "1:a:0",
            "-map_metadata", "0", "-map_chapters", "0",
            "-c:v", "copy", "-c:a", "copy", "-c:a:0", "aac", "-b:a:0", "192k",
            "-disposition:a", "0", "-disposition:a:0", "default",
            "-c:s", "copy", "-c:d", "copy", "-c:t", "copy", "-shortest",
        ]
        for audio_index in range(1, _audio_stream_count(source)):
            command.extend(["-map", f"0:a:{audio_index}"])
        command.extend(["-map", "0:s?", "-map", "0:d?", "-map", "0:t?", str(temporary_output)])
    try:
        run_ffmpeg(command)
        os.replace(temporary_output, output)
    finally:
        temporary_output.unlink(missing_ok=True)
    return output

def process_media(input_path: Path, output_path: Path, model: "WhisperModel", **options: Any) -> tuple[Path, int]:
    with tempfile.TemporaryDirectory(prefix="auto-censor-") as work:
        whisper_audio, full_audio = Path(work) / "whisper.wav", Path(work) / "full.wav"
        language = options.get("language", "ru")
        model_name = options.get("model_name", "unknown")
        cache_dir = Path(options["cache_dir"]) if options.get("cache_dir") else None
        result = _load_transcription_cache(input_path, cache_dir, model_name, language)
        if result is None:
            extract_audio(input_path, whisper_audio, full_audio)
            segments, _ = model.transcribe(str(whisper_audio), language=language, word_timestamps=True, vad_filter=True)
            result = {"segments": [{"words": [{"word": w.word, "start": w.start, "end": w.end, "probability": getattr(w, "probability", None)} for w in (segment.words or [])]} for segment in segments]}
            _save_transcription_cache(input_path, cache_dir, model_name, language, result)
        else:
            extract_full_audio(input_path, full_audio)
        censored, count = censor_audio(full_audio, result, pattern=options.get("pattern", PROFANITY_PATTERN), min_probability=options.get("min_probability"), padding_type=options.get("padding_type", "percent"), padding_start=options.get("padding_start", 20), padding_end=options.get("padding_end", 20), volume_reduction=options.get("volume_reduction", 0), fade_ms=options.get("fade_ms", 0))
        try:
            export_type = options.get("export_type", "video")
            requested_format = options.get("audio_format", "mp3")
            if count == 0 and input_path.suffix.lower() == output_path.suffix.lower():
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(input_path, output_path)
                return output_path, count
            return merge_output(input_path, censored, output_path, export_type, requested_format), count
        finally: censored.unlink(missing_ok=True)

