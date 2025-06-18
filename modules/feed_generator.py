# modules/feed_generator.py
"""
Модуль для генерации YML фида для Prom.ua
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom
import requests
import logging
from datetime import datetime
from pathlib import Path


class FeedGenerator:
    """Генератор YML фида для Prom.ua"""

    def __init__(self, config, storage):
        self.config = config
        self.storage = storage
        self.logger = logging.getLogger(__name__)

        self.output_path = Path(config.get('feed.output_path', 'feeds/prom_feed.yml'))
        self.shop_name = config.get('feed.shop_name', 'Ваш магазин')
        self.company = config.get('feed.company', 'Ваша компания')
        self.currency = config.get('feed.currency', 'UAH')
        self.margin_percent = config.get('feed.margin_percent', 10)

        # Создаём директорию для фидов
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def generate_yml_feed(self):
        """Генерирует YML фид"""
        self.logger.info("Начинаем генерацию YML фида...")

        # Получаем товары
        products = self.storage.get_products_for_feed()

        if not products:
            self.logger.warning("Нет товаров для генерации фида")
            return

        # Получаем курс валют
        pln_to_uah_rate = self._get_exchange_rate()

        # Создаём XML структуру
        yml_catalog = ET.Element('yml_catalog', date=datetime.now().strftime('%Y-%m-%d %H:%M'))
        shop = ET.SubElement(yml_catalog, 'shop')

        # Информация о магазине
        ET.SubElement(shop, 'name').text = self.shop_name
        ET.SubElement(shop, 'company').text = self.company
        ET.SubElement(shop, 'url').text = self.config.get('feed.shop_url', 'https://example.com')

        # Валюты
        currencies = ET.SubElement(shop, 'currencies')
        currency = ET.SubElement(currencies, 'currency', id=self.currency, rate='1')

        # Категории
        categories_elem = ET.SubElement(shop, 'categories')
        categories_map = self._build_categories(products, categories_elem)

        # Товары
        offers = ET.SubElement(shop, 'offers')

        for product in products:
            try:
                offer = self._create_offer(product, pln_to_uah_rate, categories_map)
                if offer is not None:
                    offers.append(offer)
            except Exception as e:
                self.logger.error(f"Ошибка при создании оффера для товара {product['id']}: {e}")

        # Сохраняем файл
        self._save_xml(yml_catalog)

        self.logger.info(f"YML фид сгенерирован: {self.output_path}")
        self.logger.info(f"Товаров в фиде: {len(offers)}")

    def _get_exchange_rate(self):
        """Получает курс PLN к UAH"""
        rate_setting = self.config.get('feed.pln_to_uah_rate', 'auto')

        if isinstance(rate_setting, (int, float)):
            return float(rate_setting)

        try:
            # Пытаемся получить актуальный курс
            response = requests.get(
                'https://api.exchangerate-api.com/v4/latest/PLN',
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            rate = data['rates'].get('UAH', 10.0)  # Fallback курс

            self.logger.info(f"Получен курс PLN/UAH: {rate}")
            return rate

        except Exception as e:
            self.logger.error(f"Ошибка получения курса валют: {e}")
            return 10.0  # Fallback курс

    def _build_categories(self, products, categories_elem):
        """Строит список категорий"""
        categories = set()

        for product in products:
            if product.get('category'):
                categories.add(product['category'])

        categories_map = {}
        category_id = 1

        for category_name in sorted(categories):
            category_elem = ET.SubElement(categories_elem, 'category', id=str(category_id))
            category_elem.text = category_name
            categories_map[category_name] = category_id
            category_id += 1

        return categories_map

    def _create_offer(self, product, pln_to_uah_rate, categories_map):
        """Создаёт элемент offer для товара"""
        # Проверяем обязательные поля
        if not product.get('title_ua') or not product.get('price'):
            return None

        # Рассчитываем цену в UAH с наценкой
        price_pln = float(product['price'])
        price_uah = price_pln * pln_to_uah_rate
        price_uah_with_margin = price_uah * (1 + self.margin_percent / 100)
        price_uah_final = round(price_uah_with_margin, 2)

        # Создаём элемент offer
        offer = ET.Element('offer', id=str(product['external_id']), available='true')

        # Основные поля
        ET.SubElement(offer, 'name').text = product['title_ua']
        ET.SubElement(offer, 'price').text = str(price_uah_final)
        ET.SubElement(offer, 'currencyId').text = self.currency

        # Категория
        if product.get('category') and product['category'] in categories_map:
            ET.SubElement(offer, 'categoryId').text = str(categories_map[product['category']])

        # Изображения
        if product.get('local_images'):
            for img_path in product['local_images'][:10]:  # Ограничиваем количество
                # Преобразуем локальный путь в URL
                img_url = self._local_path_to_url(img_path)
                if img_url:
                    ET.SubElement(offer, 'picture').text = img_url

        # Описание
        description = product.get('description_ua', '').strip()
        if description:
            description_elem = ET.SubElement(offer, 'description')
            description_elem.text = description[:3000]  # Ограничиваем длину

        # Атрибуты товара
        if product.get('brand'):
            ET.SubElement(offer, 'vendor').text = product['brand']

        if product.get('model'):
            ET.SubElement(offer, 'model').text = product['model']

        if product.get('sku'):
            ET.SubElement(offer, 'vendorCode').text = product['sku']

        # Характеристики
        if product.get('attributes_ua'):
            for attr_name, attr_value in product['attributes_ua'].items():
                if attr_name and attr_value and len(str(attr_value)) < 100:
                    param = ET.SubElement(offer, 'param', name=str(attr_name))
                    param.text = str(attr_value)

        # Наличие
        stock_status = product.get('availability', '').lower()
        if 'нет' in stock_status or 'недоступ' in stock_status:
            offer.set('available', 'false')

        # URL товара
        if product.get('url'):
            ET.SubElement(offer, 'url').text = product['url']

        return offer

    def _local_path_to_url(self, local_path):
        """Преобразует локальный путь в URL"""
        # Здесь нужно настроить базовый URL вашего сервера
        base_url = self.config.get('feed.images_base_url', 'https://yoursite.com/')

        if base_url.endswith('/'):
            base_url = base_url[:-1]

        # Убираем начальную часть пути
        relative_path = str(local_path).replace('\\', '/')
        if relative_path.startswith('./'):
            relative_path = relative_path[2:]

        return f"{base_url}/{relative_path}"

    def _save_xml(self, root):
        """Сохраняет XML в файл с красивым форматированием"""
        rough_string = ET.tostring(root, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8')

        with open(self.output_path, 'wb') as f:
            f.write(pretty_xml)
