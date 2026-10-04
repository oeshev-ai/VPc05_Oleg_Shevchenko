"""
Пример использования модуля database.

Демонстрирует создание базы, подключение, вставку, чтение,
обновление, удаление данных и работу с транзакцией.
"""

from pathlib import Path

from database import Database


# Путь к файлу базы рядом с этим скриптом
DB_PATH = Path(__file__).resolve().parent / "data" / "example.db"


def main() -> None:
    # Создаём каталог для файла БД (если его ещё нет)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Файл базы данных: {DB_PATH}")

    # Контекстный менеджер сам откроет и закроет соединение
    with Database(DB_PATH) as db:
        # --- Создание таблицы -------------------------------------------------
        if db.table_exists("books"):
            db.drop_table("books")

        db.create_table(
            "books",
            {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "title": "TEXT NOT NULL",
                "author": "TEXT NOT NULL",
                "year": "INTEGER",
                "pages": "INTEGER",
            },
        )
        print("Таблица 'books' создана.")
        print("Столбцы:", db.get_column_names("books"))

        # --- Вставка одной записи ---------------------------------------------
        book_id = db.insert(
            "books",
            {
                "title": "Мастер и Маргарита",
                "author": "Михаил Булгаков",
                "year": 1967,
                "pages": 480,
            },
        )
        print(f"Добавлена книга с id={book_id}")

        # --- Пакетная вставка -------------------------------------------------
        added = db.insert_many(
            "books",
            [
                {
                    "title": "Преступление и наказание",
                    "author": "Фёдор Достоевский",
                    "year": 1866,
                    "pages": 671,
                },
                {
                    "title": "Война и мир",
                    "author": "Лев Толстой",
                    "year": 1869,
                    "pages": 1225,
                },
                {
                    "title": "1984",
                    "author": "Джордж Оруэлл",
                    "year": 1949,
                    "pages": 328,
                },
            ],
        )
        print(f"Пакетно добавлено записей: {added}")
        print(f"Всего книг в таблице: {db.count('books')}")

        # --- Чтение всех записей ----------------------------------------------
        print("\nВсе книги:")
        for row in db.select_all("books", order_by="year"):
            print(f"  [{row['id']}] {row['title']} — {row['author']} ({row['year']})")

        # --- Чтение одной записи с условием -----------------------------------
        book = db.select_one(
            "books",
            where="title = ?",
            params=("1984",),
        )
        print("\nНайдена книга:", db.row_to_dict(book))

        # --- Обновление данных ------------------------------------------------
        updated = db.update(
            "books",
            {"pages": 350},
            where="title = ?",
            params=("1984",),
        )
        print(f"\nОбновлено строк: {updated}")

        book = db.select_one("books", where="title = ?", params=("1984",))
        print("После обновления:", db.row_to_dict(book))

        # --- Удаление данных --------------------------------------------------
        deleted = db.delete(
            "books",
            where="year < ?",
            params=(1900,),
        )
        print(f"\nУдалено старых книг: {deleted}")
        print(f"Осталось книг: {db.count('books')}")

        # --- Произвольный SQL -------------------------------------------------
        rows = db.fetch_all(
            "SELECT author, COUNT(*) AS cnt FROM books GROUP BY author"
        )
        print("\nКниг по авторам:")
        for row in rows:
            print(f"  {row['author']}: {row['cnt']}")

        # --- Транзакция -------------------------------------------------------
        with db.transaction():
            db.insert(
                "books",
                {
                    "title": "Анна Каренина",
                    "author": "Лев Толстой",
                    "year": 1877,
                    "pages": 864,
                },
            )
            db.update(
                "books",
                {"year": 1966},
                where="title = ?",
                params=("Мастер и Маргарита",),
            )
        print("\nТранзакция успешно зафиксирована.")

        print("\nИтоговое содержимое:")
        for row in db.rows_to_dicts(db.select_all("books", order_by="id")):
            print(f"  {row}")

        print("\nТаблицы в базе:", db.list_tables())

    # После выхода из with соединение уже закрыто
    print("\nСоединение закрыто.")


if __name__ == "__main__":
    main()
