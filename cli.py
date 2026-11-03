"""User-friendly command line interface for CussCut."""
from __future__ import annotations
import argparse, json, logging, os, sys
from pathlib import Path
from typing import Iterable
from faster_whisper import WhisperModel
from processor import DEFAULT_WORDS, build_pattern, process_media

MEDIA_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
LOG = logging.getLogger("cusscut")

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Автоматически заглушает нецензурные слова в видео и аудио.")
    p.add_argument("inputs", nargs="+", type=Path, metavar="INPUT", help="Медиафайл или папка")
    p.add_argument("-o", "--output", type=Path, default=Path("outputs"), help="Папка результатов")
    p.add_argument("--model", default=os.getenv("WHISPER_MODEL", "small"), help="Модель faster-whisper")
    p.add_argument("--device", choices=("cpu", "cuda"), default=os.getenv("WHISPER_DEVICE", "cpu"))
    p.add_argument("--compute-type", default=None, help="int8 для CPU, float16 для CUDA")
    p.add_argument("--language", default="ru", help="Язык речи")
    p.add_argument("--dictionary", type=Path, help="Файл словаря: одно слово или корень на строку; строки с # игнорируются")
    p.add_argument("--padding-type", choices=("percent", "ms"), default="percent")
    p.add_argument("--padding-start", type=float, default=20); p.add_argument("--padding-end", type=float, default=20)
    p.add_argument("--volume", type=float, default=0, metavar="0..1", help="Оставшаяся громкость слова; 0 = тишина")
    p.add_argument("--fade-ms", type=int, default=0, help="Плавная граница заглушки")
    p.add_argument("--format", choices=("same", "mp3", "wav", "flac", "m4a"), default="same", help="Формат аудио результата; для видео всегда MP4")
    p.add_argument("--overwrite", action="store_true"); p.add_argument("--keep-going", action="store_true"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--json", action="store_true", dest="json_output")
    return p

def load_dictionary(path: Path | None):
    if path is None: return build_pattern(DEFAULT_WORDS)
    if not path.is_file(): raise ValueError(f"Словарь не найден: {path}")
    words = [line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8-sig").splitlines()]; words = [w for w in words if w]
    if not words: raise ValueError("Словарь пустой")
    return build_pattern(words)

def collect_inputs(inputs: Iterable[Path]) -> list[Path]:
    files = []
    for item in inputs:
        if not item.exists(): raise ValueError(f"Файл или папка не найдены: {item}")
        candidates = [item] if item.is_file() else sorted(p for p in item.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS)
        for path in candidates:
            if path.suffix.lower() not in MEDIA_EXTENSIONS: raise ValueError(f"Неподдерживаемый формат: {path.suffix}")
            files.append(path.resolve())
    return list(dict.fromkeys(files))

def output_for(source: Path, output_dir: Path, fmt: str) -> Path:
    if source.suffix.lower() in VIDEO_EXTENSIONS: return output_dir / f"{source.stem}_clean.mp4"
    extension = source.suffix.lower().lstrip(".") if fmt == "same" else fmt
    if extension not in {"mp3", "wav", "flac", "m4a"}: extension = "mp3"
    return output_dir / f"{source.stem}_clean.{extension}"

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv); logging.basicConfig(level=logging.INFO, format="%(message)s")
    try: files = collect_inputs(args.inputs); pattern = load_dictionary(args.dictionary)
    except (ValueError, OSError) as exc: LOG.error("Ошибка: %s", exc); return 2
    if not files: LOG.error("Медиафайлы не найдены."); return 2
    if args.padding_start < 0 or args.padding_end < 0 or args.volume < 0 or args.volume > 1 or args.fade_ms < 0: LOG.error("Проверьте параметры отступов, fade и volume (0..1)."); return 2
    plan = [(source, output_for(source, args.output, args.format)) for source in files]
    if args.dry_run:
        for source, output in plan: print(f"{source} -> {output}")
        return 0
    compute = args.compute_type or ("int8" if args.device == "cpu" else "float16")
    try: model = WhisperModel(args.model, device=args.device, compute_type=compute)
    except Exception as exc: LOG.error("Не удалось загрузить модель: %s", exc); return 1
    results = []; options = dict(language=args.language, pattern=pattern, padding_type=args.padding_type, padding_start=args.padding_start, padding_end=args.padding_end, volume_reduction=args.volume, fade_ms=args.fade_ms, export_type="video" if files[0].suffix.lower() in VIDEO_EXTENSIONS else "audio_only", audio_format=(args.format if args.format != "same" else "mp3"))
    for index, (source, output) in enumerate(plan, 1):
        if output.exists() and not args.overwrite: LOG.warning("[%d/%d] Пропуск: %s", index, len(plan), output); results.append({"input": str(source), "status": "skipped", "output": str(output)}); continue
        LOG.info("[%d/%d] Обработка: %s", index, len(plan), source.name)
        try:
            # Audio and video are processed one at a time, keeping memory bounded.
            options["export_type"] = "video" if source.suffix.lower() in VIDEO_EXTENSIONS else "audio_only"
            options["audio_format"] = output.suffix.lower().lstrip(".")
            rendered, count = process_media(source, output, model, **options); LOG.info("  Готово: %s (заглушено: %d)", rendered, count); results.append({"input": str(source), "status": "ok", "output": str(rendered), "censored_words": count})
        except Exception as exc:
            LOG.error("  Ошибка: %s", exc); results.append({"input": str(source), "status": "error", "error": str(exc)})
            if not args.keep_going: break
    if args.json_output: print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if len(results) == len(plan) and all(x["status"] in {"ok", "skipped"} for x in results) else 1

if __name__ == "__main__": sys.exit(main())

