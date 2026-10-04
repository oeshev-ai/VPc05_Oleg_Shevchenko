"""
Smoke-тест модуля database: CRUD и базовые проверки безопасности.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# Корень проекта в PYTHONPATH при запуске из tests/
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import Database  # noqa: E402


class DatabaseSmokeTest(unittest.TestCase):
    """Проверяет основные операции Database на временной БД."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "smoke.db"
        self.db = Database(self.db_path)
        self.db.connect()
        self.db.create_table(
            "items",
            {
                "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
                "name": "TEXT NOT NULL",
                "value": "INTEGER",
            },
        )

    def tearDown(self) -> None:
        self.db.disconnect()
        self._tmpdir.cleanup()

    def test_crud(self) -> None:
        """Вставка, чтение, обновление и удаление строк."""
        row_id = self.db.insert("items", {"name": "alpha", "value": 10})
        self.assertIsInstance(row_id, int)

        row = self.db.select_one("items", where="id = ?", params=(row_id,))
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "alpha")
        self.assertEqual(row["value"], 10)

        updated = self.db.update(
            "items",
            {"value": 20},
            where="id = ?",
            params=(row_id,),
        )
        self.assertEqual(updated, 1)
        row = self.db.select_one("items", where="id = ?", params=(row_id,))
        self.assertEqual(row["value"], 20)

        deleted = self.db.delete("items", where="id = ?", params=(row_id,))
        self.assertEqual(deleted, 1)
        self.assertEqual(self.db.count("items"), 0)

    def test_columns_sql_injection_raises(self) -> None:
        """Строковые columns с опасным содержимым должны бросать ValueError."""
        with self.assertRaises(ValueError):
            self.db.select_all("items", columns="id; DROP TABLE items")

    def test_update_params_without_where_raises(self) -> None:
        """params без where в update() — ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.db.update("items", {"value": 1}, params=(1,))
        self.assertIn("params переданы без where", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
