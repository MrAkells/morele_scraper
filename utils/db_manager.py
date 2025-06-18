# utils/db_manager.py
"""
Утилиты для управления базой данных
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta


class DatabaseManager:
    """Управление базой данных парсера"""

    def __init__(self, db_path):
        self.db_path = db_path

    def backup_database(self, backup_dir='backups'):
        """Создаёт резервную копию базы данных"""
        backup_path = Path(backup_dir)
        backup_path.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_path / f"morele_parser_backup_{timestamp}.db"

        # Копируем базу данных
        import shutil
        shutil.copy2(self.db_path, backup_file)

        print(f"Backup created: {backup_file}")
        return backup_file

    def cleanup_old_data(self, days=30):
        """Очищает старые данные"""
        cutoff_date = datetime.now() - timedelta(days=days)

        with sqlite3.connect(self.db_path) as conn:
            # Удаляем старые логи парсинга
            cursor = conn.execute("""
                DELETE FROM parsing_logs
                WHERE completed_at < ?
            """, (cutoff_date.isoformat(),))

            deleted_logs = cursor.rowcount

            # Очищаем кеш переводов старше определённого времени
            cursor = conn.execute("""
                DELETE FROM translation_cache
                WHERE created_at < ?
            """, (cutoff_date.isoformat(),))

            deleted_cache = cursor.rowcount

            print(f"Deleted {deleted_logs} old parsing logs")
            print(f"Deleted {deleted_cache} old translation cache entries")

    def optimize_database(self):
        """Оптимизирует базу данных"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("VACUUM")
            conn.execute("ANALYZE")

        print("Database optimized")

    def get_database_stats(self):
        """Получает статистику базы данных"""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}

            # Количество товаров
            cursor = conn.execute("SELECT COUNT(*) FROM products")
            stats['total_products'] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
            stats['active_products'] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM products WHERE is_translated = 1")
            stats['translated_products'] = cursor.fetchone()[0]

            # Количество категорий
            cursor = conn.execute("SELECT COUNT(*) FROM categories WHERE is_active = 1")
            stats['active_categories'] = cursor.fetchone()[0]

            # Размер кеша переводов
            cursor = conn.execute("SELECT COUNT(*) FROM translation_cache")
            stats['translation_cache_size'] = cursor.fetchone()[0]

            # Размер файла БД
            db_file = Path(self.db_path)
            if db_file.exists():
                stats['db_size_mb'] = round(db_file.stat().st_size / 1024 / 1024, 2)

            return stats
