# VPc05 — база фильмов IMDB (SQLite)

Консольное приложение для работы с топ-250 фильмов IMDB: импорт из CSV, хранение в SQLite и управление через текстовое меню.

## Требования

- Python 3.10+
- Стандартная библиотека (`sqlite3`, `csv` и др.) — внешние зависимости не нужны

## Структура проекта

| Файл / каталог | Назначение |
| --- | --- |
| `database.py` | Обёртка над SQLite: подключение, CRUD, транзакции, VACUUM, backup |
| `import_imdb_csv.py` | Импорт `imdb_top_250.csv` в таблицу `movies` |
| `main.py` | Текстовый интерфейс управления БД |
| `example.py` | Учебный пример использования `Database` |
| `imdb_top_250.csv` | Исходные данные |
| `data/imdb.db` | Файл базы (создаётся при импорте / запуске) |
| `tests/test_smoke.py` | Smoke-тесты модуля `database` |

## Быстрый старт

```bash
# из корня проекта
python main.py
```

При первом запуске, если таблица пуста и рядом есть CSV, программа предложит импортировать данные.

Импорт отдельно:

```bash
python import_imdb_csv.py
```

Пример работы с модулем БД:

```bash
python example.py
```

## Меню (`main.py`)

1. Показать все фильмы (постранично)
2. Поиск фильмов (название / режиссёр / жанр / год / рейтинг)
3. Топ-10 фильмов после [год] по рейтингу
4. Добавить фильм
5. Изменить фильм
6. Удалить фильмы (по id или старше указанного года)
7. Импортировать CSV (перезаписать таблицу)
8. Оптимизировать базу (`VACUUM`)
0. Выход

Поиск по названию поддерживает:
- часть названия (`LIKE` с экранированием `%` и `_`);
- полное соответствие (без учёта регистра).

## Схема таблицы `movies`

| Столбец | Тип | Описание |
| --- | --- | --- |
| `id` | INTEGER PK | Автоинкремент |
| `rank` | INTEGER UNIQUE | Место в топе |
| `title` | TEXT | Название |
| `year` | INTEGER | Год |
| `genre` | TEXT | Жанр(ы) |
| `duration` | TEXT | Длительность |
| `origin` | TEXT | Страна / происхождение |
| `director` | TEXT | Режиссёр |
| `imdb_rating` | REAL | Рейтинг IMDB |
| `rating_count` | INTEGER | Число оценок |
| `imdb_link` | TEXT | Ссылка на IMDB |

Путь к БД по умолчанию: `data/imdb.db`.

## Использование модуля `Database`

```python
from database import Database

with Database("data/imdb.db") as db:
    rows = db.select_all(
        "movies",
        where="year > ?",
        params=(2000,),
        order_by="imdb_rating DESC",
        limit=10,
    )
    for row in rows:
        print(row["title"], row["imdb_rating"])
```

Основные возможности класса:
- контекстный менеджер и транзакции;
- `create_table` / `drop_table` / `table_exists`;
- `insert` / `insert_many` / `update` / `delete`;
- `select_all` / `select_one` / `count` / `fetch_*`;
- `vacuum`, `backup`.

## Тесты

```bash
python -m unittest tests.test_smoke -v
```

## Примечания

- Кодировка CSV: `utf-8-sig` (корректно обрабатывается BOM).
- Первый столбец в CSV без имени в заголовке — это `rank`.
- При импорте с `recreate=True` таблица `movies` пересоздаётся.
