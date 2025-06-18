# -*- coding: utf-8 -*-
"""
Morele.net Parser - главный файл
Профессиональный парсер для ежедневного сбора товаров
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Добавляем текущую директорию в путь для импортов
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from modules.parser import MoreleParser
from modules.translator import TranslationService
from modules.image_downloader import ImageDownloader
from modules.feed_generator import FeedGenerator
from modules.storage import StorageManager
from modules.admin import AdminPanel


class MoreleParserMain:
    """Главный класс для управления парсером"""

    def __init__(self, config_path='config.yaml'):
        self.config = Config(config_path)
        self.setup_logging()

        # Инициализация компонентов
        self.storage = StorageManager(self.config)
        self.translator = TranslationService(self.config, self.storage)
        self.image_downloader = ImageDownloader(self.config)
        self.parser = MoreleParser(self.config)
        self.feed_generator = FeedGenerator(self.config, self.storage)

        self.logger = logging.getLogger(__name__)

    def setup_logging(self):
        """Настройка логирования"""
        log_level = getattr(logging, self.config.get('logging.level', 'INFO').upper())

        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.get('logging.file', 'logs/parser.log')),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def run_parsing(self):
        """Основной процесс парсинга"""
        self.logger.info("Запуск парсинга товаров...")
        start_time = datetime.now()

        try:
            # Получаем список категорий для парсинга
            categories = self.storage.get_active_categories()

            if not categories:
                self.logger.warning("Нет активных категорий для парсинга")
                return

            total_new = 0
            total_updated = 0
            total_errors = 0

            for category in categories:
                self.logger.info(f"Парсинг категории: {category['url']}")

                try:
                    # Парсим товары из категории
                    products = self.parser.parse_category(category['url'])

                    for product in products:
                        try:
                            # Проверяем, есть ли товар в БД
                            existing_product = self.storage.get_product_by_url(product['url'])

                            if existing_product:
                                # Проверяем, изменился ли товар
                                if self._product_changed(existing_product, product):
                                    self._update_product(product, existing_product['id'])
                                    total_updated += 1
                            else:
                                # Новый товар
                                self._process_new_product(product)
                                total_new += 1

                        except Exception as e:
                            self.logger.error(f"Ошибка при обработке товара {product.get('url', 'unknown')}: {e}")
                            total_errors += 1

                except Exception as e:
                    self.logger.error(f"Ошибка при парсинге категории {category['url']}: {e}")
                    total_errors += 1

            # Генерируем фид
            if total_new > 0 or total_updated > 0:
                self.logger.info("Генерация YML фида...")
                self.feed_generator.generate_yml_feed()

            # Статистика
            duration = datetime.now() - start_time
            self.logger.info(f"Парсинг завершён за {duration}")
            self.logger.info(f"Новых товаров: {total_new}, обновлённых: {total_updated}, ошибок: {total_errors}")

            # Отправляем уведомление в Telegram (если настроено)
            self._send_telegram_notification(total_new, total_updated, total_errors, duration)

        except Exception as e:
            self.logger.error(f"Критическая ошибка при парсинге: {e}")
            raise

    def _product_changed(self, existing_product, new_product):
        """Проверяем, изменился ли товар"""
        # Сравниваем ключевые поля
        fields_to_compare = ['title', 'price', 'availability', 'description']

        for field in fields_to_compare:
            if existing_product.get(field) != new_product.get(field):
                return True

        return False

    def _process_new_product(self, product):
        """Обработка нового товара"""
        self.logger.debug(f"Обработка нового товара: {product['title']}")

        # Загружаем изображения
        if product.get('images'):
            local_images = self.image_downloader.download_product_images(
                product['images'],
                product['id']
            )
            product['local_images'] = local_images

        # Переводим текст
        product['title_ua'] = self.translator.translate(product['title'])
        product['description_ua'] = self.translator.translate(product['description'])

        # Переводим атрибуты
        if product.get('attributes'):
            product['attributes_ua'] = {}
            for key, value in product['attributes'].items():
                key_ua = self.translator.translate(key)
                value_ua = self.translator.translate(value) if isinstance(value, str) else value
                product['attributes_ua'][key_ua] = value_ua

        # Сохраняем в БД
        product['is_translated'] = True
        product['updated_at'] = datetime.now().isoformat()

        self.storage.save_product(product)

    def _update_product(self, product, product_id):
        """Обновление существующего товара"""
        self.logger.debug(f"Обновление товара: {product['title']}")

        # Проверяем, нужно ли обновить перевод
        existing_product = self.storage.get_product_by_id(product_id)

        if existing_product['title'] != product['title']:
            product['title_ua'] = self.translator.translate(product['title'])
        else:
            product['title_ua'] = existing_product['title_ua']

        if existing_product['description'] != product['description']:
            product['description_ua'] = self.translator.translate(product['description'])
        else:
            product['description_ua'] = existing_product['description_ua']

        # Обновляем изображения при необходимости
        if product.get('images') and product['images'] != existing_product.get('original_images'):
            local_images = self.image_downloader.download_product_images(
                product['images'],
                product['id']
            )
            product['local_images'] = local_images
        else:
            product['local_images'] = existing_product.get('local_images', [])

        product['updated_at'] = datetime.now().isoformat()
        self.storage.update_product(product_id, product)

    def _send_telegram_notification(self, new_count, updated_count, errors_count, duration):
        """Отправка уведомления в Telegram"""
        telegram_config = self.config.get('telegram')
        if not telegram_config or not telegram_config.get('enabled'):
            return

        try:
            import requests

            message = f"""🔄 Парсинг morele.net завершён

📊 Статистика:
• Новых товаров: {new_count}
• Обновлённых: {updated_count}
• Ошибок: {errors_count}
• Время выполнения: {duration}

📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"""

            url = f"https://api.telegram.org/bot{telegram_config['bot_token']}/sendMessage"
            data = {
                'chat_id': telegram_config['chat_id'],
                'text': message,
                'parse_mode': 'HTML'
            }

            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                self.logger.info("Telegram уведомление отправлено")
            else:
                self.logger.error(f"Ошибка отправки Telegram уведомления: {response.text}")

        except Exception as e:
            self.logger.error(f"Ошибка при отправке Telegram уведомления: {e}")

    def run_admin_panel(self, host='127.0.0.1', port=5000):
        """Запуск веб-админки"""
        admin = AdminPanel(self.config, self.storage)
        admin.run(host=host, port=port)


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Morele.net Parser')
    parser.add_argument('--config', default='config.yaml', help='Путь к файлу конфигурации')
    parser.add_argument('--admin', action='store_true', help='Запустить веб-админку')
    parser.add_argument('--host', default='127.0.0.1', help='Host для админки')
    parser.add_argument('--port', type=int, default=5000, help='Порт для админки')
    parser.add_argument('--parse', action='store_true', help='Запустить парсинг')
    parser.add_argument('--generate-feed', action='store_true', help='Сгенерировать YML фид')

    args = parser.parse_args()

    # Создаём необходимые директории
    Path('logs').mkdir(exist_ok=True)
    Path('data').mkdir(exist_ok=True)
    Path('images').mkdir(exist_ok=True)
    Path('feeds').mkdir(exist_ok=True)

    try:
        app = MoreleParserMain(args.config)

        if args.admin:
            print(f"Запуск админ-панели на http://{args.host}:{args.port}")
            app.run_admin_panel(args.host, args.port)
        elif args.parse:
            app.run_parsing()
        elif args.generate_feed:
            app.feed_generator.generate_yml_feed()
            print("YML фид сгенерирован")
        else:
            print("Используйте --parse для парсинга или --admin для запуска админки")
            print("Для помощи: python main.py --help")

    except KeyboardInterrupt:
        print("\nПарсинг прерван пользователем")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        logging.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
