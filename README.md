# CussCut

CussCut — CLI для автоматической цензуры нецензурной речи в аудио и видео. Whisper распознаёт речь с таймкодами, а FFmpeg заглушает найденные интервалы, сохраняя длительность записи.

Поддерживаются CPU и CUDA, обработка одного файла или каталога, пользовательские словари, кеш таймкодов и Docker.

## Установка

Требуется Python 3.10+ и FFmpeg в `PATH`.

```powershell
python -m pip install cusscut
```

После установки доступны три одинаковые команды:

```text
cusscut
ccut
ccus
```

Для установки последней версии прямо из GitHub:

```powershell
python -m pip install "git+https://github.com/1wm9k/cusscut.git"
```

При первом запуске `faster-whisper` скачает выбранную модель. Модель хранится в кеше Hugging Face и повторно не скачивается.

## Быстрый старт

```powershell
ccus input.mp4 -o outputs
ccus input.mp3 -o outputs
ccus .\media -o outputs --keep-going
```

Видео сохраняются в MP4. Для аудио формат по умолчанию берётся из исходного файла, если он поддерживается результатом.

```powershell
ccus input.mp3 --format flac -o outputs
ccus input.wav --format m4a -o outputs
ccus input.ogg -o outputs       # результат будет MP3
```

При обработке каталога output-папка исключается из поиска, вложенная структура сохраняется, а одинаковые имена не перезаписывают друг друга.

## Основные параметры

```powershell
ccus input.mp4 `
  --model small `
  --device cpu `
  --compute-type int8 `
  --language ru `
  --volume 0 `
  --fade-ms 30
```

| Параметр | Назначение |
| --- | --- |
| `--model` | Модель `faster-whisper`; по умолчанию `small`. |
| `--device` | `cpu` или `cuda`. |
| `--compute-type` | Например, `int8` для CPU или `float16` для CUDA. |
| `--language` | Язык речи, например `ru` или `en`. |
| `--volume` | Остаточная громкость заглушенного фрагмента от `0` до `1`. |
| `--fade-ms` | Плавное начало и окончание заглушки. |
| `--padding-type` | `percent` или `ms`. |
| `--padding-start`, `--padding-end` | Сколько убрать с краёв распознанного слова. |
| `--match-mode` | `substring`, `prefix` или `exact`. |
| `--min-probability` | Минимальная уверенность Whisper для срабатывания. |
| `--format` | `same`, `mp3`, `wav`, `flac` или `m4a`. Для видео всегда MP4. |
| `--cache-dir` | Папка кеша таймкодов Whisper. |
| `--overwrite` | Перезаписать существующие результаты. |
| `--keep-going` | Продолжить пакет после ошибки. |
| `--dry-run` | Показать план без загрузки модели. |
| `--json` | Вывести результат или план в JSON. |

## Словарь

Файл содержит одно слово или корень на строку. Пустые строки и комментарии после `#` игнорируются.

```text
# words.txt
мат
ругательствослово
```

```powershell
ccus input.mp4 --dictionary words.txt --match-mode prefix
```

Режимы сопоставления:

- `substring` — ищет фрагмент внутри слова; это режим по умолчанию;
- `prefix` — ищет корень в начале слова;
- `exact` — требует полное совпадение.

Перед сопоставлением текст нормализуется в Unicode, приводится к нижнему регистру, а `ё` и `е` считаются одинаковыми. Внешний словарь заменяет встроенный.

## Кеш распознавания

Кеш позволяет менять громкость, fade, padding и словарь без повторного запуска Whisper:

```powershell
ccus input.mp4 --cache-dir .cusscut-cache
ccus input.mp4 --cache-dir .cusscut-cache --volume 0.15 --fade-ms 50
```

Запись кеша зависит от пути, размера и даты изменения исходника, модели и языка. При изменении этих параметров распознавание выполняется заново.

## Результаты и потоки

Для видео сохраняются дополнительные аудиодорожки, субтитры и metadata. Новая цензурированная аудиодорожка становится первой. Если слова не найдены и формат результата совпадает с исходным, файл копируется без перекодирования.

Результаты записываются атомарно через временный файл, поэтому прерванная обработка не должна оставлять готовый на вид повреждённый MP4.

## Docker

```powershell
docker build -t cusscut .
docker run --rm -v "${PWD}:/data" cusscut /data/input.mp4 -o /data/outputs
```

Чтобы не скачивать модель заново:

```powershell
docker run --rm `
  -v "${PWD}:/data" `
  -v "whisper-cache:/root/.cache" `
  cusscut /data/input.mp4 -o /data/outputs
```

## Разработка

```powershell
python -m pip install -e ".[dev]"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -m pytest
python -m build
```

Сборка создаёт wheel и source distribution в `dist/`.

## CI/CD и PyPI

GitHub Actions запускает тесты и сборку на push и pull request. Workflow `publish.yml` публикует пакет в PyPI на каждый push в `main` и при ручном запуске.

Для push-публикаций workflow берёт базовую версию из `pyproject.toml` и добавляет номер запуска GitHub Actions. Например:

```text
0.1.0.post12
```

Чтобы начать новую основную версию, измени `version` в `pyproject.toml`, например на `0.2.0`, и отправь commit в `main`.

## Ссылки

- [GitHub](https://github.com/1wm9k/cusscut)
- [PyPI](https://pypi.org/project/cusscut/)
- [Техническое описание проекта](TECHNICAL.md)

