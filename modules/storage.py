# modules/storage.py
"""
Модуль для работы с хранилищем данных
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path


class StorageManager:
    """Менеджер для работы с базой данных"""

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Инициализация БД
        self.db_type = config.get('database.type', 'sqlite')

        if self.db_type == 'sqlite':
            self.db_path = config.get('database.sqlite_path', 'data/morele_parser.db')
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()
        else:
            raise NotImplementedError("Пока поддерживается только SQLite")

    def _init_sqlite(self):
        """Инициализирует SQLite базу данных"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    title_ua TEXT,
                    price REAL NOT NULL,
                    availability TEXT,
                    description TEXT,
                    description_ua TEXT,
                    attributes TEXT,
                    attributes_ua TEXT,
                    category TEXT,
                    brand TEXT,
                    model TEXT,
                    sku TEXT,
                    images TEXT,
                    local_images TEXT,
                    content_hash TEXT,
                    is_translated BOOLEAN DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS translation_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_text TEXT UNIQUE NOT NULL,
                    translated_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS parsing_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_url TEXT,
                    products_found INTEGER,
                    products_new INTEGER,
                    products_updated INTEGER,
                    errors_count INTEGER,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_products_external_id ON products(external_id);
                CREATE INDEX IF NOT EXISTS idx_products_url ON products(url);
                CREATE INDEX IF NOT EXISTS idx_translation_cache_original ON translation_cache(original_text);
            """)

    def save_product(self, product):
        """Сохраняет товар в базу данных"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO products (
                    external_id, url, title, title_ua, price, availability,
                    description, description_ua, attributes, attributes_ua,
                    category, brand, model, sku, images, local_images,
                    content_hash, is_translated, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product['id'],
                product['url'],
                product['title'],
                product.get('title_ua', ''),
                product['price'],
                product['availability'],
                product['description'],
                product.get('description_ua', ''),
                json.dumps(product.get('attributes', {}), ensure_ascii=False),
                json.dumps(product.get('attributes_ua', {}), ensure_ascii=False),
                product.get('category', ''),
                product.get('brand', ''),
                product.get('model', ''),
                product.get('sku', ''),
                json.dumps(product.get('images', [])),
                json.dumps(product.get('local_images', [])),
                product.get('content_hash', ''),
                product.get('is_translated', False),
                datetime.now().isoformat()
            ))

    def get_product_by_url(self, url):
        """Получает товар по URL"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM products WHERE url = ?", (url,))
            row = cursor.fetchone()

            if row:
                product = dict(row)
                product['attributes'] = json.loads(product['attributes'] or '{}')
                product['attributes_ua'] = json.loads(product['attributes_ua'] or '{}')
                product['images'] = json.loads(product['images'] or '[]')
                product['local_images'] = json.loads(product['local_images'] or '[]')
                return product

        return None

    def get_product_by_id(self, product_id):
        """Получает товар по ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
            row = cursor.fetchone()

            if row:
                product = dict(row)
                product['attributes'] = json.loads(product['attributes'] or '{}')
                product['attributes_ua'] = json.loads(product['attributes_ua'] or '{}')
                product['images'] = json.loads(product['images'] or '[]')
                product['local_images'] = json.loads(product['local_images'] or '[]')
                return product

        return None

    def update_product(self, product_id, product_data):
        """Обновляет товар"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE products SET
                    title = ?, title_ua = ?, price = ?, availability = ?,
                    description = ?, description_ua = ?, attributes = ?, attributes_ua = ?,
                    category = ?, brand = ?, model = ?, sku = ?, images = ?, local_images = ?,
                    content_hash = ?, is_translated = ?, updated_at = ?
                WHERE id = ?
            """, (
                product_data['title'],
                product_data.get('title_ua', ''),
                product_data['price'],
                product_data['availability'],
                product_data['description'],
                product_data.get('description_ua', ''),
                json.dumps(product_data.get('attributes', {}), ensure_ascii=False),
                json.dumps(product_data.get('attributes_ua', {}), ensure_ascii=False),
                product_data.get('category', ''),
                product_data.get('brand', ''),
                product_data.get('model', ''),
                product_data.get('sku', ''),
                json.dumps(product_data.get('images', [])),
                json.dumps(product_data.get('local_images', [])),
                product_data.get('content_hash', ''),
                product_data.get('is_translated', False),
                datetime.now().isoformat(),
                product_id
            ))

    def get_active_categories(self):
        """Получает список активных категорий для парсинга"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM categories WHERE is_active = 1")
            return [dict(row) for row in cursor.fetchall()]

    def add_category(self, name, url):
        """Добавляет категорию"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO categories (name, url) VALUES (?, ?)
            """, (name, url))

    def deactivate_category(self, category_id):
        """Деактивирует категорию"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE categories SET is_active = 0 WHERE id = ?", (category_id,))

    def get_translation_from_cache(self, original_text):
        """Получает перевод из кеша"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT translated_text FROM translation_cache WHERE original_text = ?",
                (original_text,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def save_translation_to_cache(self, original_text, translated_text):
        """Сохраняет перевод в кеш"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO translation_cache (original_text, translated_text)
                VALUES (?, ?)
            """, (original_text, translated_text))

    def get_products_for_feed(self):
        """Получает товары для генерации фида"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM products
                WHERE is_active = 1 AND is_translated = 1 AND price > 0
                ORDER BY updated_at DESC
            """)

            products = []
            for row in cursor.fetchall():
                product = dict(row)
                product['attributes'] = json.loads(product['attributes'] or '{}')
                product['attributes_ua'] = json.loads(product['attributes_ua'] or '{}')
                product['images'] = json.loads(product['images'] or '[]')
                product['local_images'] = json.loads(product['local_images'] or '[]')
                products.append(product)

            return products

    def log_parsing_session(self, category_url, stats):
        """Логирует сессию парсинга"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO parsing_logs
                (category_url, products_found, products_new, products_updated, errors_count, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                category_url,
                stats.get('found', 0),
                stats.get('new', 0),
                stats.get('updated', 0),
                stats.get('errors', 0),
                stats.get('started_at'),
                stats.get('completed_at')
            ))

    def get_parsing_stats(self, days=30):
        """Получает статистику парсинга за последние дни"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM parsing_logs
                WHERE completed_at > datetime('now', '-{} days')
                ORDER BY completed_at DESC
            """.format(days))

            return [dict(row) for row in cursor.fetchall()]
