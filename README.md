# auto-censor

CLI для автоматической цензуры нецензурной речи в видео и аудиофайлах. Whisper находит слова с таймкодами, приложение заглушает середину слова и сохраняет исходную длину файла.

## Установка

Нужны Python 3.10+ и FFmpeg в `PATH`.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

При первом запуске faster-whisper скачает модель. Для слабого CPU используйте `--model tiny` или `--model base`.

## Запуск

```bash
python cli.py input.mp4 -o outputs
python cli.py input.mp3 --format flac -o outputs
python cli.py ./media --keep-going --overwrite
python cli.py input.mp4 --device cuda --compute-type float16
```

Поддерживаются видео `mp4, mov, mkv, avi, webm, m4v` и аудио `mp3, wav, flac, m4a, ogg, aac`. Папка обрабатывается рекурсивно. Видео сохраняются в MP4 с исходной видеодорожкой, аудио по умолчанию сохраняется в исходном формате (`--format same`).

Полезные параметры:

- `--padding-type percent|ms`, `--padding-start`, `--padding-end` — сколько оставить по краям слова;
- `--volume 0..1` — остаточная громкость цензурируемого фрагмента;
- `--fade-ms` — плавная граница заглушки;
- `--dictionary words.txt` — свой словарь, по одному слову или корню на строку; комментарии после `#` игнорируются;
- `--dry-run` — показать план без загрузки модели;
- `--json` — вывести результаты в JSON;
- `--keep-going` — продолжить пакет при ошибке.

Пример словаря:

```text
# корни работают для производных слов
матерный_корень
другое_слово
```

## Docker

```bash
docker build -t auto-censor .
docker run --rm -v "${PWD}:/data" auto-censor /data/input.mp4 -o /data/outputs
```

Для Windows PowerShell:

```powershell
docker run --rm -v "${PWD}:/data" auto-censor /data/input.mp4 -o /data/outputs
```

Модель кэшируется внутри контейнера только на время его жизни. Чтобы не скачивать её заново, подключите каталог кеша faster-whisper отдельным volume.

## Проверка

```bash
python -m pytest
python cli.py input.mp4 --dry-run
```
