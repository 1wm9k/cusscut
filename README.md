# CussCut

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

Полная команда — `cusscut`, короткий алиас — `ccut`. Они работают одинаково.

```bash
cusscut input.mp4 -o outputs
cusscut input.mp3 -o outputs
cusscut ./media --keep-going --overwrite
```

Также можно запускать напрямую:

```bash
python cli.py input.mp4 -o outputs
```

Видео сохраняются в MP4 с исходной видеодорожкой. Для аудио по умолчанию сохраняется исходный поддерживаемый формат:

```bash
ccut input.mp3 --format flac -o outputs
ccut input.wav --format m4a -o outputs
ccut input.ogg -o outputs  # неподдерживаемый для вывода OGG будет сохранён как MP3
```

## Настройки

```bash
ccut input.mp4 \
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
- `--match-mode substring|prefix|exact` — режим сопоставления словаря; по умолчанию ищется подстрока, `prefix` подходит для корней, `exact` требует полное совпадение;
- `--min-probability 0..1` — минимальная уверенность Whisper для срабатывания;
- `--cache-dir PATH` — сохранять таймкоды распознавания для повторного рендеринга без запуска Whisper;
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
ccut input.mp4 --dictionary words.txt
```

При использовании `--dictionary` он заменяет стандартный словарь.

Кеш таймкодов учитывает путь, размер и дату изменения исходника, модель и язык. Если любой из этих параметров изменился, файл распознаётся заново.

Перед сопоставлением слова нормализуются в Unicode и приводятся к нижнему регистру; `ё` и `е` считаются одинаковыми. Для длинных корней рекомендуется `--match-mode prefix`.

При обработке видео сохраняются дополнительные аудиодорожки, субтитры и metadata, а цензурированная дорожка становится первой. Если в файле не найдено ни одного слова и формат результата совпадает с исходным, файл копируется без перекодирования.

## Docker

```bash
docker build -t cusscut .
docker run --rm \
  -v "${PWD}:/data" \
  cusscut /data/input.mp4 -o /data/outputs
```

PowerShell:

```powershell
docker run --rm -v "${PWD}:/data" cusscut /data/input.mp4 -o /data/outputs
```

Чтобы модель не скачивалась заново при каждом запуске контейнера, подключите кеш:

```bash
docker run --rm \
  -v "${PWD}:/data" \
  -v "whisper-cache:/root/.cache" \
  cusscut /data/input.mp4 -o /data/outputs
```

Для CUDA используйте образ с поддержкой NVIDIA и добавьте `--gpus all`, затем передайте `--device cuda --compute-type float16`.

## Проверка проекта

```bash
python -m pytest
python cli.py input.mp4 --dry-run
```

Тесты проверяют распознавание слов, границы таймкодов и объединение перекрывающихся интервалов.

