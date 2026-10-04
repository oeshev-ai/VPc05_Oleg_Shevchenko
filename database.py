"""
Модуль для работы с базой данных SQLite3.

Предоставляет класс Database с методами подключения, чтения,
вставки, обновления, удаления и вспомогательными операциями.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator, Iterable, Mapping, Optional, Sequence, Union


Params = Union[Sequence[Any], Mapping[str, Any]]


class Database:
    """
    Класс-обёртка над SQLite3 для удобной работы с базой данных.

    Поддерживает контекстный менеджер: при выходе из блока ``with``
    соединение автоматически закрывается.

    Пример использования::

        with Database("movies.db") as db:
            db.create_table(
                "films",
                {
                    "id": "INTEGER PRIMARY KEY",
                    "title": "TEXT NOT NULL",
                    "year": "INTEGER",
                },
            )
            db.insert("films", {"title": "Inception", "year": 2010})
            rows = db.select_all("films")
    """

    def __init__(
        self,
        db_path: Union[str, Path] = "database.db",
        *,
        timeout: float = 5.0,
        check_same_thread: bool = True,
        row_factory: bool = True,
    ) -> None:
        """
        Инициализирует объект базы данных.

        :param db_path: путь к файлу базы данных SQLite
        :param timeout: время ожидания блокировки (в секундах)
        :param check_same_thread: запрещать ли использование соединения
            из другого потока (поведение sqlite3 по умолчанию)
        :param row_factory: если True, строки возвращаются как sqlite3.Row
            (доступ по имени столбца и по индексу)
        """
        self.db_path = Path(db_path)
        self.timeout = timeout
        self.check_same_thread = check_same_thread
        self.row_factory = row_factory
        self._connection: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------
    # Контекстный менеджер и свойства
    # ------------------------------------------------------------------

    def __enter__(self) -> "Database":
        """Открывает соединение при входе в блок ``with``."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Закрывает соединение при выходе из блока ``with``.

        При исключении выполняется откат транзакции, иначе — фиксация.
        """
        if self._connection is None:
            return

        try:
            if exc_type is not None:
                self.rollback()
            else:
                self.commit()
        finally:
            self.disconnect()

    @property
    def connection(self) -> sqlite3.Connection:
        """
        Возвращает активное соединение с базой данных.

        :raises RuntimeError: если соединение ещё не установлено
        """
        if self._connection is None:
            raise RuntimeError(
                "Соединение с базой данных не установлено. "
                "Вызовите connect() или используйте контекстный менеджер."
            )
        return self._connection

    @property
    def is_connected(self) -> bool:
        """Проверяет, установлено ли соединение с базой данных."""
        return self._connection is not None

    # ------------------------------------------------------------------
    # Подключение / отключение
    # ------------------------------------------------------------------

    def connect(self) -> sqlite3.Connection:
        """
        Устанавливает соединение с базой данных.

        Если файл базы не существует, он будет создан автоматически.
        Повторный вызов при уже открытом соединении возвращает его же.

        :return: объект соединения sqlite3.Connection
        """
        if self._connection is not None:
            return self._connection

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(self.db_path),
            timeout=self.timeout,
            check_same_thread=self.check_same_thread,
        )
        if self.row_factory:
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def disconnect(self) -> None:
        """
        Закрывает соединение с базой данных.

        Безопасно вызывается повторно, если соединение уже закрыто.
        """
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def close(self) -> None:
        """Псевдоним для disconnect() — закрывает соединение."""
        self.disconnect()

    @contextmanager
    def cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Контекстный менеджер для работы с курсором.

        Курсор автоматически закрывается при выходе из блока.

        Пример::

            with db.cursor() as cur:
                cur.execute("SELECT 1")
        """
        cur = self.connection.cursor()
        try:
            yield cur
        finally:
            cur.close()

    @contextmanager
    def transaction(self) -> Generator["Database", None, None]:
        """
        Контекстный менеджер транзакции.

        При успешном завершении блока изменения фиксируются (commit),
        при исключении — откатываются (rollback).

        Пример::

            with db.transaction():
                db.insert("films", {"title": "A"})
                db.insert("films", {"title": "B"})
        """
        try:
            yield self
            self.commit()
        except Exception:
            self.rollback()
            raise

    # ------------------------------------------------------------------
    # Транзакции
    # ------------------------------------------------------------------

    def commit(self) -> None:
        """Фиксирует текущую транзакцию (сохраняет изменения)."""
        self.connection.commit()

    def rollback(self) -> None:
        """Откатывает текущую транзакцию (отменяет изменения)."""
        self.connection.rollback()

    # ------------------------------------------------------------------
    # Выполнение SQL
    # ------------------------------------------------------------------

    def execute(
        self,
        sql: str,
        params: Params = (),
        *,
        commit: bool = False,
    ) -> sqlite3.Cursor:
        """
        Выполняет один SQL-запрос.

        :param sql: текст SQL-запроса (можно с плейсхолдерами ``?`` или ``:name``)
        :param params: параметры запроса (кортеж/список или словарь)
        :param commit: если True, сразу фиксирует изменения
        :return: курсор с результатом выполнения
        """
        cur = self.connection.execute(sql, params)
        if commit:
            self.commit()
        return cur

    def executemany(
        self,
        sql: str,
        seq_of_params: Iterable[Params],
        *,
        commit: bool = False,
    ) -> sqlite3.Cursor:
        """
        Выполняет один SQL-запрос для набора параметров (пакетная вставка и т.п.).

        :param sql: текст SQL-запроса
        :param seq_of_params: последовательность наборов параметров
        :param commit: если True, сразу фиксирует изменения
        :return: курсор с результатом выполнения
        """
        cur = self.connection.executemany(sql, seq_of_params)
        if commit:
            self.commit()
        return cur

    def executescript(self, script: str) -> sqlite3.Cursor:
        """
        Выполняет SQL-скрипт из нескольких операторов.

        SQLite сам фиксирует изменения внутри executescript,
        отдельный commit не требуется.

        :param script: текст скрипта (операторы разделяются ``;``)
        :return: курсор с результатом выполнения
        """
        return self.connection.executescript(script)

    # ------------------------------------------------------------------
    # Работа с таблицами
    # ------------------------------------------------------------------

    def create_table(
        self,
        table: str,
        columns: Mapping[str, str],
        *,
        if_not_exists: bool = True,
        commit: bool = True,
    ) -> None:
        """
        Создаёт таблицу с заданными столбцами.

        :param table: имя таблицы
        :param columns: словарь ``{имя_столбца: определение SQL}``,
            например ``{"id": "INTEGER PRIMARY KEY", "title": "TEXT NOT NULL"}``
        :param if_not_exists: не создавать таблицу заново, если она уже есть
        :param commit: фиксировать изменения сразу
        """
        self._validate_identifier(table)
        defs = []
        for name, definition in columns.items():
            self._validate_identifier(name)
            defs.append(f'"{name}" {definition}')

        exists = "IF NOT EXISTS " if if_not_exists else ""
        sql = f'CREATE TABLE {exists}"{table}" ({", ".join(defs)})'
        self.execute(sql, commit=commit)

    def drop_table(
        self,
        table: str,
        *,
        if_exists: bool = True,
        commit: bool = True,
    ) -> None:
        """
        Удаляет таблицу целиком.

        :param table: имя таблицы
        :param if_exists: не вызывать ошибку, если таблицы нет
        :param commit: фиксировать изменения сразу
        """
        self._validate_identifier(table)
        exists = "IF EXISTS " if if_exists else ""
        self.execute(f'DROP TABLE {exists}"{table}"', commit=commit)

    def table_exists(self, table: str) -> bool:
        """
        Проверяет, существует ли таблица в базе данных.

        :param table: имя таблицы
        :return: True, если таблица найдена
        """
        row = self.fetch_one(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        )
        return row is not None

    def list_tables(self) -> list[str]:
        """
        Возвращает список имён всех пользовательских таблиц.

        :return: список имён таблиц
        """
        rows = self.fetch_all(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        return [row[0] if not isinstance(row, sqlite3.Row) else row["name"] for row in rows]

    def get_table_info(self, table: str) -> list[dict[str, Any]]:
        """
        Возвращает информацию о столбцах таблицы (PRAGMA table_info).

        :param table: имя таблицы
        :return: список словарей с полями cid, name, type, notnull, dflt_value, pk
        """
        self._validate_identifier(table)
        rows = self.fetch_all(f'PRAGMA table_info("{table}")')
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "cid": self._row_get(row, "cid", 0),
                    "name": self._row_get(row, "name", 1),
                    "type": self._row_get(row, "type", 2),
                    "notnull": self._row_get(row, "notnull", 3),
                    "dflt_value": self._row_get(row, "dflt_value", 4),
                    "pk": self._row_get(row, "pk", 5),
                }
            )
        return result

    def get_column_names(self, table: str) -> list[str]:
        """
        Возвращает список имён столбцов таблицы.

        :param table: имя таблицы
        :return: имена столбцов
        """
        return [col["name"] for col in self.get_table_info(table)]

    # ------------------------------------------------------------------
    # Чтение данных
    # ------------------------------------------------------------------

    def fetch_one(
        self,
        sql: str,
        params: Params = (),
    ) -> Optional[Any]:
        """
        Выполняет SELECT и возвращает одну строку (или None).

        :param sql: SQL-запрос
        :param params: параметры запроса
        :return: одна строка результата или None
        """
        cur = self.execute(sql, params)
        return cur.fetchone()

    def fetch_all(
        self,
        sql: str,
        params: Params = (),
    ) -> list[Any]:
        """
        Выполняет SELECT и возвращает все строки.

        :param sql: SQL-запрос
        :param params: параметры запроса
        :return: список строк результата
        """
        cur = self.execute(sql, params)
        return cur.fetchall()

    def fetch_many(
        self,
        sql: str,
        params: Params = (),
        size: int = 1,
    ) -> list[Any]:
        """
        Выполняет SELECT и возвращает ограниченное число строк.

        :param sql: SQL-запрос
        :param params: параметры запроса
        :param size: максимальное число строк
        :return: список строк результата
        """
        cur = self.execute(sql, params)
        return cur.fetchmany(size)

    def fetch_value(
        self,
        sql: str,
        params: Params = (),
        default: Any = None,
    ) -> Any:
        """
        Выполняет SELECT и возвращает значение первой ячейки первой строки.

        Удобно для запросов вида ``SELECT COUNT(*) ...``.

        :param sql: SQL-запрос
        :param params: параметры запроса
        :param default: значение, если результат пуст
        :return: скалярное значение или default
        """
        row = self.fetch_one(sql, params)
        if row is None:
            return default
        return row[0]

    def select_all(
        self,
        table: str,
        columns: Sequence[str] | str = "*",
        *,
        where: Optional[str] = None,
        params: Params = (),
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[Any]:
        """
        Выбирает строки из таблицы с опциональными условиями.

        :param table: имя таблицы
        :param columns: список столбцов или ``"*"``
        :param where: условие WHERE без ключевого слова WHERE
            (например, ``"year > ?"``)
        :param params: параметры для условия WHERE
        :param order_by: выражение ORDER BY без ключевого слова
        :param limit: ограничение числа строк
        :param offset: смещение выборки
        :return: список строк
        """
        sql = self._build_select_sql(
            table,
            columns,
            where=where,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return self.fetch_all(sql, params)

    def select_one(
        self,
        table: str,
        columns: Sequence[str] | str = "*",
        *,
        where: Optional[str] = None,
        params: Params = (),
        order_by: Optional[str] = None,
    ) -> Optional[Any]:
        """
        Выбирает одну строку из таблицы.

        :param table: имя таблицы
        :param columns: список столбцов или ``"*"``
        :param where: условие WHERE без ключевого слова WHERE
        :param params: параметры для условия WHERE
        :param order_by: выражение ORDER BY без ключевого слова
        :return: одна строка или None
        """
        sql = self._build_select_sql(
            table,
            columns,
            where=where,
            order_by=order_by,
            limit=1,
        )
        return self.fetch_one(sql, params)

    def count(
        self,
        table: str,
        *,
        where: Optional[str] = None,
        params: Params = (),
    ) -> int:
        """
        Возвращает количество строк в таблице (с опциональным условием).

        :param table: имя таблицы
        :param where: условие WHERE без ключевого слова WHERE
        :param params: параметры для условия WHERE
        :return: число строк
        """
        self._validate_identifier(table)
        sql = f'SELECT COUNT(*) FROM "{table}"'
        if where:
            sql += f" WHERE {where}"
        return int(self.fetch_value(sql, params, default=0))

    # ------------------------------------------------------------------
    # Вставка данных
    # ------------------------------------------------------------------

    def insert(
        self,
        table: str,
        data: Mapping[str, Any],
        *,
        or_ignore: bool = False,
        or_replace: bool = False,
        commit: bool = True,
    ) -> Optional[int]:
        """
        Вставляет одну запись в таблицу.

        :param table: имя таблицы
        :param data: словарь ``{столбец: значение}``
        :param or_ignore: использовать INSERT OR IGNORE
        :param or_replace: использовать INSERT OR REPLACE
        :param commit: фиксировать изменения сразу
        :return: id последней вставленной строки (lastrowid);
            ``None``, если вставка проигнорирована из-за конфликта
            (``or_ignore=True`` и ``rowcount == 0``)
        """
        if not data:
            raise ValueError("Словарь data не должен быть пустым.")

        self._validate_identifier(table)
        for key in data:
            self._validate_identifier(key)

        conflict = ""
        if or_replace:
            conflict = "OR REPLACE "
        elif or_ignore:
            conflict = "OR IGNORE "

        columns = ", ".join(f'"{col}"' for col in data)
        placeholders = ", ".join("?" for _ in data)
        sql = (
            f'INSERT {conflict}INTO "{table}" ({columns}) '
            f"VALUES ({placeholders})"
        )
        cur = self.execute(sql, tuple(data.values()), commit=commit)
        if or_ignore and cur.rowcount == 0:
            return None
        return int(cur.lastrowid or 0)

    def insert_many(
        self,
        table: str,
        rows: Sequence[Mapping[str, Any]],
        *,
        or_ignore: bool = False,
        or_replace: bool = False,
        commit: bool = True,
    ) -> int:
        """
        Вставляет несколько записей в таблицу одним запросом.

        Все словари должны содержать одинаковый набор ключей
        (порядок берётся из первой записи).

        :param table: имя таблицы
        :param rows: последовательность словарей
        :param or_ignore: использовать INSERT OR IGNORE
        :param or_replace: использовать INSERT OR REPLACE
        :param commit: фиксировать изменения сразу
        :return: число затронутых строк (rowcount);
            на некоторых сборках SQLite может быть ``-1``
        """
        if not rows:
            return 0

        first = rows[0]
        if not first:
            raise ValueError("Словари rows не должны быть пустыми.")

        self._validate_identifier(table)
        keys = list(first.keys())
        key_set = set(keys)
        for key in keys:
            self._validate_identifier(key)

        for index, row in enumerate(rows):
            if set(row.keys()) != key_set:
                raise ValueError(
                    f"Строка #{index} имеет другой набор ключей: "
                    f"{sorted(row.keys())}, ожидалось: {sorted(keys)}"
                )

        conflict = ""
        if or_replace:
            conflict = "OR REPLACE "
        elif or_ignore:
            conflict = "OR IGNORE "

        columns = ", ".join(f'"{col}"' for col in keys)
        placeholders = ", ".join("?" for _ in keys)
        sql = (
            f'INSERT {conflict}INTO "{table}" ({columns}) '
            f"VALUES ({placeholders})"
        )
        params = [tuple(row[key] for key in keys) for row in rows]
        cur = self.executemany(sql, params, commit=commit)
        return cur.rowcount

    # ------------------------------------------------------------------
    # Обновление данных
    # ------------------------------------------------------------------

    def update(
        self,
        table: str,
        data: Mapping[str, Any],
        *,
        where: Optional[str] = None,
        params: Params = (),
        commit: bool = True,
    ) -> int:
        """
        Обновляет записи в таблице.

        :param table: имя таблицы
        :param data: словарь ``{столбец: новое_значение}``
        :param where: условие WHERE без ключевого слова WHERE;
            если не указано, обновляются все строки
        :param params: параметры для условия WHERE
            (позиционные ``?`` или именованные ``:name``);
            нельзя передавать без ``where``
        :param commit: фиксировать изменения сразу
        :return: число обновлённых строк
        """
        if not data:
            raise ValueError("Словарь data не должен быть пустым.")
        if params and where is None:
            raise ValueError("params переданы без where")

        self._validate_identifier(table)
        for key in data:
            self._validate_identifier(key)

        if where and isinstance(params, Mapping):
            set_clause = ", ".join(f'"{col}" = :set_{col}' for col in data)
            sql = f'UPDATE "{table}" SET {set_clause} WHERE {where}'
            values: dict[str, Any] = {f"set_{col}": v for col, v in data.items()}
            values.update(params)
            cur = self.execute(sql, values, commit=commit)
        else:
            set_clause = ", ".join(f'"{col}" = ?' for col in data)
            sql = f'UPDATE "{table}" SET {set_clause}'
            values_list: list[Any] = list(data.values())
            if where:
                sql += f" WHERE {where}"
                values_list.extend(params)
            cur = self.execute(sql, tuple(values_list), commit=commit)
        return cur.rowcount

    # ------------------------------------------------------------------
    # Удаление данных
    # ------------------------------------------------------------------

    def delete(
        self,
        table: str,
        *,
        where: Optional[str] = None,
        params: Params = (),
        commit: bool = True,
    ) -> int:
        """
        Удаляет записи из таблицы.

        :param table: имя таблицы
        :param where: условие WHERE без ключевого слова WHERE;
            если не указано, удаляются все строки
        :param params: параметры для условия WHERE;
            нельзя передавать без ``where``
        :param commit: фиксировать изменения сразу
        :return: число удалённых строк
        """
        if params and where is None:
            raise ValueError("params переданы без where")

        self._validate_identifier(table)
        sql = f'DELETE FROM "{table}"'
        if where:
            sql += f" WHERE {where}"
        cur = self.execute(sql, params, commit=commit)
        return cur.rowcount

    def truncate(
        self,
        table: str,
        *,
        commit: bool = True,
    ) -> int:
        """
        Удаляет все строки из таблицы (аналог TRUNCATE через DELETE).

        :param table: имя таблицы
        :param commit: фиксировать изменения сразу
        :return: число удалённых строк
        """
        return self.delete(table, commit=commit)

    # ------------------------------------------------------------------
    # Служебные / удобные методы
    # ------------------------------------------------------------------

    def vacuum(self) -> None:
        """
        Выполняет VACUUM — пересобирает файл БД и освобождает место.
        """
        self.execute("VACUUM")

    def backup(self, destination: Union[str, Path]) -> None:
        """
        Создаёт резервную копию базы данных в указанный файл.

        :param destination: путь к файлу копии
        """
        dest_path = Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_conn = sqlite3.connect(str(dest_path))
        try:
            self.connection.backup(dest_conn)
            dest_conn.commit()
        finally:
            dest_conn.close()

    def enable_foreign_keys(self, enabled: bool = True) -> None:
        """
        Включает или отключает проверку внешних ключей (PRAGMA foreign_keys).

        :param enabled: True — включить, False — выключить
        """
        self.execute(f"PRAGMA foreign_keys = {1 if enabled else 0}")

    def last_insert_rowid(self) -> int:
        """
        Возвращает rowid последней вставленной строки в текущем соединении.

        :return: идентификатор последней вставки
        """
        return int(self.fetch_value("SELECT last_insert_rowid()", default=0))

    def row_to_dict(self, row: Any) -> Optional[dict[str, Any]]:
        """
        Преобразует строку результата (sqlite3.Row или кортеж) в словарь.

        Для кортежа без имён столбцов возвращает словарь с ключами
        ``col_0``, ``col_1``, ...

        :param row: строка результата или None
        :return: словарь или None
        """
        if row is None:
            return None
        if isinstance(row, sqlite3.Row):
            return dict(row)
        if isinstance(row, Mapping):
            return dict(row)
        return {f"col_{i}": value for i, value in enumerate(row)}

    def rows_to_dicts(self, rows: Sequence[Any]) -> list[dict[str, Any]]:
        """
        Преобразует список строк результата в список словарей.

        :param rows: список строк (sqlite3.Row и т.п.)
        :return: список словарей
        """
        result: list[dict[str, Any]] = []
        for row in rows:
            as_dict = self.row_to_dict(row)
            if as_dict is not None:
                result.append(as_dict)
        return result

    # ------------------------------------------------------------------
    # Внутренние вспомогательные методы
    # ------------------------------------------------------------------

    @staticmethod
    def _row_get(row: Any, key: str, idx: int) -> Any:
        """
        Возвращает значение из строки результата по имени или индексу.

        Для ``sqlite3.Row`` используется ключ, иначе — позиционный индекс.
        """
        if isinstance(row, sqlite3.Row):
            return row[key]
        return row[idx]

    def _build_select_sql(
        self,
        table: str,
        columns: Sequence[str] | str = "*",
        *,
        where: Optional[str] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> str:
        """Собирает SELECT-запрос из отдельных частей."""
        self._validate_identifier(table)

        if columns == "*" or columns is None:
            cols = "*"
        elif isinstance(columns, str):
            parts = [c.strip() for c in columns.split(",")]
            for c in parts:
                if c != "*":
                    self._validate_identifier(c)
            cols = ", ".join(c if c == "*" else f'"{c}"' for c in parts)
        else:
            for col in columns:
                if col != "*":
                    self._validate_identifier(col)
            cols = ", ".join(
                col if col == "*" else f'"{col}"' for col in columns
            )

        sql = f'SELECT {cols} FROM "{table}"'
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        if offset is not None:
            sql += f" OFFSET {int(offset)}"
        return sql

    @staticmethod
    def _validate_identifier(name: str) -> None:
        """
        Проверяет, что идентификатор (имя таблицы/столбца) безопасен.

        Разрешены буквы, цифры и подчёркивание; имя не может начинаться с цифры.
        """
        if not name or not isinstance(name, str):
            raise ValueError("Имя таблицы или столбца должно быть непустой строкой.")
        if not name.replace("_", "").isalnum() or name[0].isdigit():
            raise ValueError(
                f"Недопустимое имя идентификатора: {name!r}. "
                "Используйте буквы, цифры и подчёркивание."
            )


__all__ = ["Database"]
