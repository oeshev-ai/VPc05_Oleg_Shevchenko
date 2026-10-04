"""
Текстовый интерфейс для управления базой данных фильмов IMDB.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

from database import Database
from import_imdb_csv import (
    CSV_PATH,
    DB_PATH,
    TABLE_NAME,
    TABLE_SCHEMA,
    import_csv_to_db,
)


SEPARATOR = "-" * 72


def ensure_database() -> None:
    """Создаёт каталог и таблицу movies, если их ещё нет."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with Database(DB_PATH) as db:
        if not db.table_exists(TABLE_NAME):
            db.create_table(TABLE_NAME, TABLE_SCHEMA)
            print(f"Создана пустая таблица '{TABLE_NAME}' в {DB_PATH}")


def offer_import_if_empty() -> None:
    """
    Предлагает импорт из CSV, если таблица movies пуста.

    Спрашивает подтверждение только при наличии файла CSV.
    """
    with Database(DB_PATH) as db:
        if db.count(TABLE_NAME) > 0:
            return

    if not CSV_PATH.exists():
        return

    if ask_confirm("База пуста. Импортировать данные из CSV? (y/n)", default=False):
        count = import_csv_to_db(CSV_PATH, DB_PATH, recreate=True)
        print(f"Импортировано фильмов: {count}")


def pause() -> None:
    """Пауза до нажатия Enter."""
    input("\nНажмите Enter, чтобы продолжить...")


def ask(prompt: str, *, default: Optional[str] = None) -> str:
    """
    Запрашивает строку у пользователя.

    :param prompt: текст приглашения
    :param default: значение по умолчанию (Enter без ввода)
    """
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{prompt}{suffix}: ").strip()
    if not value and default is not None:
        return default
    return value


def ask_confirm(prompt: str, *, default: bool = False) -> bool:
    """
    Запрашивает подтверждение (y/n / да/нет).

    :param prompt: текст приглашения
    :param default: значение по умолчанию при пустом вводе
    :return: True, если пользователь подтвердил
    """
    default_str = "y" if default else "n"
    value = ask(prompt, default=default_str).lower()
    return value in {"y", "yes", "д", "да"}

def ask_int(prompt: str, *, default: Optional[int] = None) -> Optional[int]:
    """Запрашивает целое число. Пустой ввод → default или None."""
    while True:
        raw = ask(prompt, default=str(default) if default is not None else None)
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            print("Введите целое число.")


def ask_float(prompt: str, *, default: Optional[float] = None) -> Optional[float]:
    """Запрашивает число с плавающей точкой. Пустой ввод → default или None."""
    while True:
        raw = ask(
            prompt,
            default=str(default) if default is not None else None,
        )
        if not raw:
            return default
        try:
            return float(raw.replace(",", "."))
        except ValueError:
            print("Введите число, например 8.5")


def ask_optional(prompt: str, current: Any = None) -> Optional[str]:
    """
    Запрос необязательного поля при редактировании.

    Enter сохраняет текущее значение; '-' очищает поле.
    """
    current_text = "" if current is None else str(current)
    hint = f" (Enter — оставить «{current_text}», '-' — очистить)"
    value = input(f"{prompt}{hint}: ").strip()
    if value == "":
        return current_text
    if value == "-":
        return None
    return value


def _fmt(value: Any, *, width: Optional[int] = None, default: str = "?") -> str:
    """
    Безопасно форматирует значение для вывода в консоль.

    :param value: исходное значение (``None`` и пустая строка → default)
    :param width: ширина выравнивания вправо; если None — без выравнивания
    :param default: текст-заглушка для пустых значений
    :return: строка для печати
    """
    if value is None or value == "":
        text = default
    else:
        text = str(value)
    return f"{text:>{width}}" if width else text


def format_movie(row: Any, *, detailed: bool = False) -> str:
    """Форматирует запись фильма для вывода в консоль."""
    data = dict(row)
    line = (
        f"#{_fmt(data.get('rank'), width=3)} | "
        f"{_fmt(data.get('title'), default='')} "
        f"({_fmt(data.get('year'))}) | "
        f"IMDB {_fmt(data.get('imdb_rating'))} | "
        f"{_fmt(data.get('director'), default='')}"
    )
    if not detailed:
        return line

    return (
        f"{line}\n"
        f"     id={_fmt(data.get('id'))} | жанр: {_fmt(data.get('genre'), default='')}\n"
        f"     длительность: {_fmt(data.get('duration'), default='')} | "
        f"страна: {_fmt(data.get('origin'), default='')}\n"
        f"     оценок: {_fmt(data.get('rating_count'))} | "
        f"{_fmt(data.get('imdb_link'), default='')}"
    )


def _escape_like(text: str) -> str:
    """
    Экранирует спецсимволы LIKE (``\\``, ``%``, ``_``) в строке поиска.

    :param text: исходный текст пользователя
    :return: строка, безопасная для ``LIKE ... ESCAPE '\\'``
    """
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def print_movies(rows: list[Any], *, detailed: bool = False) -> None:
    """Печатает список фильмов."""
    if not rows:
        print("Ничего не найдено.")
        return
    print(SEPARATOR)
    for row in rows:
        print(format_movie(row, detailed=detailed))
    print(SEPARATOR)
    print(f"Показано записей: {len(rows)}")


def next_rank(db: Database) -> int:
    """Возвращает следующий свободный rank (max + 1)."""
    value = db.fetch_value(f'SELECT MAX(rank) FROM "{TABLE_NAME}"', default=0)
    return int(value or 0) + 1


def show_menu() -> None:
    """Печатает главное меню."""
    print()
    print("=" * 72)
    print("  УПРАВЛЕНИЕ БАЗОЙ ФИЛЬМОВ IMDB")
    print(f"  Файл БД: {DB_PATH}")
    print("=" * 72)
    print("  1. Показать все фильмы")
    print("  2. Поиск фильмов")
    print("  3. Топ-10 фильмов после [год] по рейтингу")
    print("  4. Добавить фильм")
    print("  5. Изменить фильм")
    print("  6. Удалить фильмы")
    print("  7. Импортировать CSV (перезаписать таблицу)")
    print("  8. Оптимизировать базу (VACUUM)")
    print("  0. Выход")
    print("=" * 72)


def action_list_all() -> str:
    """
    Показывает фильмы с постраничным выводом.

    :return: ``"skip_pause"`` — лишняя пауза после пейджинга не нужна
    """
    page_size = ask_int("Сколько записей на странице", default=20) or 20
    page = 1

    with Database(DB_PATH) as db:
        total = db.count(TABLE_NAME)
        if total == 0:
            print("База пуста.")
            return "skip_pause"

        while True:
            offset = (page - 1) * page_size
            rows = db.select_all(
                TABLE_NAME,
                order_by="rank ASC",
                limit=page_size,
                offset=offset,
            )
            pages = max(1, (total + page_size - 1) // page_size)
            print(f"\nСтраница {page}/{pages} (всего {total})")
            print_movies(rows)

            if pages == 1:
                break

            cmd = ask("n — дальше, p — назад, q — в меню", default="q").lower()
            if cmd == "n" and page < pages:
                page += 1
            elif cmd == "p" and page > 1:
                page -= 1
            else:
                break

    return "skip_pause"


def action_search() -> None:
    """Поиск по названию, режиссёру, жанру или году."""
    print("\nПоиск по:")
    print("  1. Названию")
    print("  2. Режиссёру")
    print("  3. Жанру")
    print("  4. Году")
    print("  5. Минимальному рейтингу")
    choice = ask("Выбор", default="1")

    where = ""
    params: tuple[Any, ...] = ()

    if choice == "1":
        print("\nПоиск по названию:")
        print("  1. По части названия")
        print("  2. Полное соответствие")
        title_mode = ask("Выбор", default="1")

        if title_mode == "1":
            text = ask("Часть названия")
            if not text:
                print("Название не указано.")
                return
            where = "title LIKE ? ESCAPE '\\'"
            params = (f"%{_escape_like(text)}%",)
        elif title_mode == "2":
            text = ask("Точное название")
            if not text:
                print("Название не указано.")
                return
            where = "title = ? COLLATE NOCASE"
            params = (text,)
        else:
            print("Неизвестный пункт.")
            return
    elif choice == "2":
        text = ask("Часть имени режиссёра")
        if not text:
            print("Имя режиссёра не указано.")
            return
        where = "director LIKE ? ESCAPE '\\'"
        params = (f"%{_escape_like(text)}%",)
    elif choice == "3":
        text = ask("Часть жанра (например Drama)")
        if not text:
            print("Жанр не указан.")
            return
        where = "genre LIKE ? ESCAPE '\\'"
        params = (f"%{_escape_like(text)}%",)
    elif choice == "4":
        year = ask_int("Год")
        if year is None:
            print("Год не указан.")
            return
        where = "year = ?"
        params = (year,)
    elif choice == "5":
        rating = ask_float("Минимальный рейтинг")
        if rating is None:
            print("Рейтинг не указан.")
            return
        where = "imdb_rating >= ?"
        params = (rating,)
    else:
        print("Неизвестный пункт.")
        return

    with Database(DB_PATH) as db:
        rows = db.select_all(
            TABLE_NAME,
            where=where,
            params=params,
            order_by="imdb_rating DESC, rank ASC",
        )
        print_movies(rows)


def collect_movie_fields(
    *,
    defaults: Optional[dict[str, Any]] = None,
    editing: bool = False,
) -> Optional[dict[str, Any]]:
    """
    Собирает поля фильма с консоли.

    :param defaults: текущие значения при редактировании
    :param editing: режим изменения существующей записи
    """
    defaults = defaults or {}

    if editing:
        title = ask_optional("Название", defaults.get("title"))
        year_raw = ask_optional("Год", defaults.get("year"))
        genre = ask_optional("Жанр", defaults.get("genre"))
        duration = ask_optional("Длительность", defaults.get("duration"))
        origin = ask_optional("Страна / происхождение", defaults.get("origin"))
        director = ask_optional("Режиссёр", defaults.get("director"))
        rating_raw = ask_optional("Рейтинг IMDB", defaults.get("imdb_rating"))
        count_raw = ask_optional("Число оценок", defaults.get("rating_count"))
        link = ask_optional("Ссылка IMDB", defaults.get("imdb_link"))
        rank_raw = ask_optional("Rank в топе", defaults.get("rank"))
    else:
        title = ask("Название")
        year_raw = ask("Год")
        genre = ask("Жанр", default="")
        duration = ask("Длительность (например 2h 22min)", default="")
        origin = ask("Страна / происхождение", default="")
        director = ask("Режиссёр", default="")
        rating_raw = ask("Рейтинг IMDB", default="0")
        count_raw = ask("Число оценок", default="0")
        link = ask("Ссылка IMDB", default="")
        rank_raw = ask("Rank в топе (Enter — автоматически)", default="")

    if not title:
        print("Название обязательно.")
        return None

    try:
        year = int(year_raw) if year_raw not in (None, "") else None
        imdb_rating = (
            float(str(rating_raw).replace(",", "."))
            if rating_raw not in (None, "")
            else None
        )
        rating_count = int(count_raw) if count_raw not in (None, "") else None
        rank = int(rank_raw) if rank_raw not in (None, "") else None
    except ValueError:
        print("Ошибка: год, рейтинг, число оценок и rank должны быть числами.")
        return None

    return {
        "title": title,
        "year": year,
        "genre": genre or None,
        "duration": duration or None,
        "origin": origin or None,
        "director": director or None,
        "imdb_rating": imdb_rating,
        "rating_count": rating_count,
        "imdb_link": link or None,
        "rank": rank,
    }


def action_add() -> None:
    """Добавляет новый фильм."""
    print("\nДобавление фильма (обязательно только название):")
    data = collect_movie_fields()
    if data is None:
        return

    with Database(DB_PATH) as db:
        if data["rank"] is None:
            data["rank"] = next_rank(db)

        exists = db.select_one(TABLE_NAME, where="rank = ?", params=(data["rank"],))
        if exists is not None:
            print(f"Rank {data['rank']} уже занят. Укажите другой.")
            return

        movie_id = db.insert(TABLE_NAME, data)
        print(f"Фильм добавлен (id={movie_id}, rank={data['rank']}).")


def action_update() -> None:
    """Изменяет существующий фильм."""
    movie_id = ask_int("id фильма для изменения")
    if movie_id is None:
        print("id не указан.")
        return

    with Database(DB_PATH) as db:
        row = db.select_one(TABLE_NAME, where="id = ?", params=(movie_id,))
        if row is None:
            print("Фильм не найден.")
            return

        print("\nТекущие данные:")
        print(format_movie(row, detailed=True))
        print("\nВведите новые значения:")

        data = collect_movie_fields(defaults=dict(row), editing=True)
        if data is None:
            return

        if data["rank"] is None:
            print("Rank не может быть пустым.")
            return

        conflict = db.select_one(
            TABLE_NAME,
            where="rank = ? AND id != ?",
            params=(data["rank"], movie_id),
        )
        if conflict is not None:
            print(f"Rank {data['rank']} уже занят другим фильмом.")
            return

        updated = db.update(TABLE_NAME, data, where="id = ?", params=(movie_id,))
        print(f"Обновлено записей: {updated}")


def action_delete_by_id() -> None:
    """Удаляет один фильм по id."""
    movie_id = ask_int("id фильма для удаления")
    if movie_id is None:
        print("id не указан.")
        return

    with Database(DB_PATH) as db:
        row = db.select_one(TABLE_NAME, where="id = ?", params=(movie_id,))
        if row is None:
            print("Фильм не найден.")
            return

        print("Будет удалён:")
        print(format_movie(row, detailed=True))
        if not ask_confirm("Подтвердить удаление? (y/n)", default=False):
            print("Отменено.")
            return

        deleted = db.delete(TABLE_NAME, where="id = ?", params=(movie_id,))
        print(f"Удалено записей: {deleted}")


def action_delete_older_than_year() -> None:
    """Удаляет все фильмы старше указанного года (year < год)."""
    year = ask_int("Удалить фильмы старше года")
    if year is None:
        print("Год не указан.")
        return

    with Database(DB_PATH) as db:
        to_delete = db.count(TABLE_NAME, where="year < ?", params=(year,))
        if to_delete == 0:
            print(f"Фильмов старше {year} не найдено.")
            return

        print(f"\nБудет удалено фильмов старше {year}: {to_delete}")
        preview = db.select_all(
            TABLE_NAME,
            where="year < ?",
            params=(year,),
            order_by="year ASC, rank ASC",
            limit=10,
        )
        print("Примеры (до 10 штук):")
        print_movies(preview)

        if not ask_confirm("Подтвердить удаление? (y/n)", default=False):
            print("Отменено.")
            return

        deleted = db.delete(TABLE_NAME, where="year < ?", params=(year,))
        print(f"Удалено записей: {deleted}")
        print(f"Осталось в базе: {db.count(TABLE_NAME)}")


def action_delete() -> None:
    """Меню удаления фильмов."""
    print("\nУдаление:")
    print("  1. Удалить фильм по id")
    print("  2. Удалить фильмы старше [год]")
    print("  0. Назад")
    choice = ask("Выбор", default="0")

    if choice == "1":
        action_delete_by_id()
    elif choice == "2":
        action_delete_older_than_year()
    elif choice == "0":
        return
    else:
        print("Неизвестный пункт.")


def action_import_csv() -> None:
    """Импортирует CSV с перезаписью таблицы."""
    if not CSV_PATH.exists():
        print(f"CSV не найден: {CSV_PATH}")
        return

    if not ask_confirm(
        "Таблица будет пересоздана и заполнена из CSV. Продолжить? (y/n)",
        default=False,
    ):
        print("Отменено.")
        return

    count = import_csv_to_db(CSV_PATH, DB_PATH, recreate=True)
    print(f"Импортировано фильмов: {count}")


def action_top10_after_year() -> None:
    """Показывает топ-10 фильмов, снятых после указанного года, по рейтингу."""
    year = ask_int("Показать топ-10 фильмов после года", default=2000)
    if year is None:
        print("Год не указан.")
        return

    with Database(DB_PATH) as db:
        total_after = db.count(TABLE_NAME, where="year > ?", params=(year,))
        rows = db.select_all(
            TABLE_NAME,
            where="year > ?",
            params=(year,),
            order_by="imdb_rating DESC, rank ASC",
            limit=10,
        )

        print(f"\nТоп-10 фильмов после {year} по рейтингу")
        print(f"(всего таких фильмов в базе: {total_after})")
        print_movies(rows)


def _format_size(size: int) -> str:
    """Форматирует размер файла в читаемый вид."""
    if size < 1024:
        return f"{size} Б"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} КБ"
    return f"{size / (1024 * 1024):.2f} МБ"


def action_vacuum() -> None:
    """Оптимизирует файл базы данных командой VACUUM."""
    if not DB_PATH.exists():
        print(f"Файл базы не найден: {DB_PATH}")
        return

    size_before = DB_PATH.stat().st_size
    print(f"Размер базы до оптимизации: {_format_size(size_before)}")

    with Database(DB_PATH) as db:
        db.vacuum()

    size_after = DB_PATH.stat().st_size
    freed = size_before - size_after
    print(f"Размер базы после оптимизации: {_format_size(size_after)}")
    if freed > 0:
        print(f"Освобождено: {_format_size(freed)}")
    else:
        print("Освободить место не удалось — база уже компактна.")
    print("Оптимизация (VACUUM) завершена.")


def main() -> None:
    """Главный цикл текстового интерфейса."""
    ensure_database()
    offer_import_if_empty()

    actions = {
        "1": action_list_all,
        "2": action_search,
        "3": action_top10_after_year,
        "4": action_add,
        "5": action_update,
        "6": action_delete,
        "7": action_import_csv,
        "8": action_vacuum,
    }

    while True:
        show_menu()
        choice = ask("Пункт меню", default="0")

        if choice == "0":
            print("Выход.")
            break

        action = actions.get(choice)
        if action is None:
            print("Неизвестный пункт меню.")
            pause()
            continue

        try:
            result = action()
        except KeyboardInterrupt:
            print("\nОперация прервана.")
            result = None
        except Exception as exc:  # noqa: BLE001 — интерфейс показывает ошибку пользователю
            print(f"Ошибка: {exc}")
            result = None

        if result != "skip_pause":
            pause()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nВыход.")
        sys.exit(0)
