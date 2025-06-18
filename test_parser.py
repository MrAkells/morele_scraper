# test_parser.py
"""
Тестирование функциональности парсера
"""

import unittest
import tempfile
import os
import json
from pathlib import Path
import sys

# Добавляем путь к модулям
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from modules.storage import StorageManager
from modules.translator import TranslationService
from modules.feed_generator import FeedGenerator


class TestConfig(unittest.TestCase):
    """Тестирование конфигурации"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.temp_dir, 'test_config.yaml')

    def test_config_creation(self):
        """Тест создания конфигурации"""
        config = Config(self.config_path)

        # Проверяем, что файл создался
        self.assertTrue(os.path.exists(self.config_path))

        # Проверяем базовые настройки
        self.assertIsNotNone(config.get('database.type'))
        self.assertIsNotNone(config.get('parsing.user_agent'))

    def test_config_get_set(self):
        """Тест получения и установки значений"""
        config = Config(self.config_path)

        # Установка значения
        config.set('test.value', 'test_data')
        self.assertEqual(config.get('test.value'), 'test_data')

        # Получение несуществующего значения
        self.assertIsNone(config.get('nonexistent.key'))
        self.assertEqual(config.get('nonexistent.key', 'default'), 'default')


class TestStorage(unittest.TestCase):
    """Тестирование хранилища"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = Config()
        self.config.config['database']['sqlite_path'] = os.path.join(self.temp_dir, 'test.db')
        self.storage = StorageManager(self.config)

    def test_product_operations(self):
        """Тест операций с товарами"""
        # Тестовый товар
        product = {
            'id': 'test_123',
            'url': 'https://test.com/product/123',
            'title': 'Test Product',
            'price': 99.99,
            'availability': 'в наличии',
            'description': 'Test description',
            'category': 'Test Category',
            'images': ['https://test.com/img1.jpg'],
            'content_hash': 'test_hash'
        }

        # Сохранение товара
        self.storage.save_product(product)

        # Получение товара
        saved_product = self.storage.get_product_by_url(product['url'])
        self.assertIsNotNone(saved_product)
        self.assertEqual(saved_product['title'], product['title'])
        self.assertEqual(saved_product['price'], product['price'])

    def test_category_operations(self):
        """Тест операций с категориями"""
        # Добавление категории
        self.storage.add_category('Test Category', 'https://test.com/category')

        # Получение активных категорий
        categories = self.storage.get_active_categories()
        self.assertEqual(len(categories), 1)
        self.assertEqual(categories[0]['name'], 'Test Category')

    def test_translation_cache(self):
        """Тест кеша переводов"""
        original = "Test text"
        translated = "Тестовый текст"

        # Сохранение в кеш
        self.storage.save_translation_to_cache(original, translated)

        # Получение из кеша
        cached = self.storage.get_translation_from_cache(original)
        self.assertEqual(cached, translated)

        # Несуществующий перевод
        not_found = self.storage.get_translation_from_cache("Not found")
        self.assertIsNone(not_found)


class TestFeedGenerator(unittest.TestCase):
    """Тестирование генератора фида"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = Config()
        self.config.config['database']['sqlite_path'] = os.path.join(self.temp_dir, 'test.db')
        self.config.config['feed']['output_path'] = os.path.join(self.temp_dir, 'test_feed.yml')

        self.storage = StorageManager(self.config)
        self.feed_generator = FeedGenerator(self.config, self.storage)

        # Добавляем тестовый товар
        product = {
            'external_id': 'test_123',
            'url': 'https://test.com/product/123',
            'title': 'Test Product',
            'title_ua': 'Тестовий товар',
            'price': 100.0,
            'availability': 'в наличии',
            'description': 'Test description',
            'description_ua': 'Тестовий опис',
            'category': 'Test Category',
            'brand': 'Test Brand',
            'images': ['https://test.com/img1.jpg'],
            'local_images': ['images/test_123/img1.jpg'],
            'is_translated': True,
            'is_active': True
        }

        self.storage.save_product(product)

    def test_feed_generation(self):
        """Тест генерации фида"""
        self.feed_generator.generate_yml_feed()

        # Проверяем, что файл создался
        feed_path = self.config.get('feed.output_path')
        self.assertTrue(os.path.exists(feed_path))

        # Проверяем содержимое
        with open(feed_path, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn('yml_catalog', content)
        self.assertIn('shop', content)
        self.assertIn('offers', content)
        self.assertIn('Тестовий товар', content)
