"""
Скрипт импорта файла imdb_top_250.csv в базу данных SQLite.

Использует модуль database.Database для создания таблицы и записи данных.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Optional

from database import Database


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "imdb_top_250.csv"
DB_PATH = BASE_DIR / "data" / "imdb.db"
TABLE_NAME = "movies"


# Соответствие: заголовок CSV → имя столбца в БД
CSV_TO_DB_COLUMNS = {
    "": "rank",  # первый столбец в CSV без имени
    "Title": "title",
    "Year": "year",
    "Genre": "genre",
    "Duration": "duration",
    "Origin": "origin",
    "Director": "director",
    "IMDB rating": "imdb_rating",
    "Rating count": "rating_count",
    "IMDB link": "imdb_link",
}

TABLE_SCHEMA = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "rank": "INTEGER NOT NULL UNIQUE",
    "title": "TEXT NOT NULL",
    "year": "INTEGER",
    "genre": "TEXT",
    "duration": "TEXT",
    "origin": "TEXT",
    "director": "TEXT",
    "imdb_rating": "REAL",
    "rating_count": "INTEGER",
    "imdb_link": "TEXT",
}


def _to_int(value: str) -> Optional[int]:
    """
    Преобразует строку в int; пустая строка даёт None.

    :param value: исходное строковое значение
    :return: целое число или None
    """
    value = value.strip()
    return int(value) if value else None


def _to_float(value: str) -> Optional[float]:
    """
    Преобразует строку в float; пустая строка даёт None.

    Допускает запятую как десятичный разделитель.

    :param value: исходное строковое значение
    :return: число с плавающей точкой или None
    """
    value = value.strip().replace(",", ".")
    return float(value) if value else None


def read_movies_from_csv(csv_path: Path) -> list[dict]:
    """
    Читает CSV с топ-250 фильмов IMDB и возвращает список словарей для вставки.

    Первый столбец CSV не имеет имени в заголовке (пустая строка ``""``)
    и соответствует полю ``rank``.

    :param csv_path: путь к CSV-файлу
    :return: список записей с ключами, соответствующими столбцам таблицы
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV-файл не найден: {csv_path}")

    movies: list[dict] = []

    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        expected = set(CSV_TO_DB_COLUMNS)
        actual = set(reader.fieldnames or [])
        missing = expected - actual
        if missing:
            raise ValueError(f"В CSV отсутствуют ожидаемые столбцы: {sorted(missing)}")

        for row in reader:
            try:
                rank = int(row[""])
            except (ValueError, KeyError) as exc:
                raise ValueError(
                    f"Некорректный rank в строке CSV №{reader.line_num}"
                ) from exc

            movies.append(
                {
                    "rank": rank,
                    "title": row["Title"].strip(),
                    "year": _to_int(row["Year"]),
                    "genre": row["Genre"].strip(),
                    "duration": row["Duration"].strip(),
                    "origin": row["Origin"].strip(),
                    "director": row["Director"].strip(),
                    "imdb_rating": _to_float(row["IMDB rating"]),
                    "rating_count": _to_int(row["Rating count"]),
                    "imdb_link": row["IMDB link"].strip(),
                }
            )

    return movies


def import_csv_to_db(
    csv_path: Path = CSV_PATH,
    db_path: Path = DB_PATH,
    *,
    recreate: bool = True,
) -> int:
    """
    Импортирует данные из CSV в SQLite.

    :param csv_path: путь к CSV-файлу
    :param db_path: путь к файлу базы данных
    :param recreate: если True, пересоздаёт таблицу перед импортом
    :return: число импортированных строк (длина списка из CSV)
    """
    movies = read_movies_from_csv(csv_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with Database(db_path) as db:
        if recreate and db.table_exists(TABLE_NAME):
            db.drop_table(TABLE_NAME)

        if not db.table_exists(TABLE_NAME):
            db.create_table(TABLE_NAME, TABLE_SCHEMA)

        try:
            db.insert_many(TABLE_NAME, movies)
        except sqlite3.IntegrityError as exc:
            raise RuntimeError(
                "Конфликт уникальности rank, возможно, в CSV есть дубликаты"
            ) from exc

        return len(movies)


def main() -> None:
    print(f"CSV: {CSV_PATH}")
    print(f"БД:  {DB_PATH}")

    count = import_csv_to_db()
    print(f"Импортировано фильмов: {count}")

    with Database(DB_PATH) as db:
        total = db.count(TABLE_NAME)
        print(f"Всего записей в таблице '{TABLE_NAME}': {total}")

        print("\nТоп-5 по рейтингу IMDB:")
        top = db.select_all(
            TABLE_NAME,
            columns=("rank", "title", "year", "imdb_rating", "director"),
            order_by="imdb_rating DESC, rank ASC",
            limit=5,
        )
        for row in top:
            print(
                f"  #{row['rank']:3}  {row['title']} ({row['year']}) "
                f"— {row['imdb_rating']} — {row['director']}"
            )


if __name__ == "__main__":
    main()
