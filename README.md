# auto-censor

CLI для автоматической цензуры нецензурной речи в аудио и видео. `faster-whisper` распознаёт речь с таймкодами, а программа заглушает найденные фрагменты, сохраняя исходную длину записи.

## Возможности

- видео: MP4, MOV, MKV, AVI, WebM, M4V;
- аудио: MP3, WAV, FLAC, M4A, OGG, AAC;
- обработка одного файла или папки рекурсивно;
- CPU по умолчанию и CUDA при наличии совместимой видеокарты;
- пользовательский словарь слов и корней;
- пакетная обработка без загрузки всех файлов в память;
- Docker-запуск без ручной установки FFmpeg.

## Установка

Нужны Python 3.10+ и FFmpeg в `PATH`.

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS
# source .venv/bin/activate
pip install -e .
```

При первом запуске `faster-whisper` скачает выбранную модель. Для слабого CPU используйте `--model tiny` или `--model base`.

## Быстрый запуск

```bash
auto-censor input.mp4 -o outputs
auto-censor input.mp3 -o outputs
auto-censor ./media --keep-going --overwrite
```

Также можно запускать напрямую:

```bash
python cli.py input.mp4 -o outputs
```

Видео сохраняются в MP4 с исходной видеодорожкой. Для аудио по умолчанию сохраняется исходный поддерживаемый формат:

```bash
auto-censor input.mp3 --format flac -o outputs
auto-censor input.wav --format m4a -o outputs
auto-censor input.ogg -o outputs  # неподдерживаемый для вывода OGG будет сохранён как MP3
```

## Настройки

```bash
auto-censor input.mp4 \
  --model small \
  --language ru \
  --padding-type percent \
  --padding-start 20 \
  --padding-end 20 \
  --volume 0 \
  --fade-ms 30
```

- `--padding-type percent|ms` — единицы отступов вокруг слова;
- `--padding-start`, `--padding-end` — сколько оставить в начале и конце слова;
- `--volume 0..1` — остаточная громкость заглушенного фрагмента, `0` означает тишину;
- `--fade-ms` — плавное начало и окончание заглушки;
- `--format same|mp3|wav|flac|m4a` — формат аудио результата;
- `--overwrite` — перезаписать существующие результаты;
- `--keep-going` — продолжить пакет после ошибки;
- `--dry-run` — показать план без загрузки модели;
- `--json` — вывести итог в JSON.

## Внешний словарь

Файл словаря содержит одно слово или корень на строку. Пустые строки и комментарии после `#` игнорируются.

`words.txt`:

```text
# Можно указывать корни, чтобы ловить производные формы
мат
ругательствослово
```

Запуск:

```bash
auto-censor input.mp4 --dictionary words.txt
```

При использовании `--dictionary` он заменяет стандартный словарь.

## Docker

```bash
docker build -t auto-censor .
docker run --rm \
  -v "${PWD}:/data" \
  auto-censor /data/input.mp4 -o /data/outputs
```

PowerShell:

```powershell
docker run --rm -v "${PWD}:/data" auto-censor /data/input.mp4 -o /data/outputs
```

Чтобы модель не скачивалась заново при каждом запуске контейнера, подключите кеш:

```bash
docker run --rm \
  -v "${PWD}:/data" \
  -v "whisper-cache:/root/.cache" \
  auto-censor /data/input.mp4 -o /data/outputs
```

Для CUDA используйте образ с поддержкой NVIDIA и добавьте `--gpus all`, затем передайте `--device cuda --compute-type float16`.

## Проверка проекта

```bash
python -m pytest
python cli.py input.mp4 --dry-run
```

Тесты проверяют распознавание слов, границы таймкодов и объединение перекрывающихся интервалов.
