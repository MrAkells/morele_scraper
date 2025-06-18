# utils/feed_validator.py
"""
Валидатор YML фида
"""

import xml.etree.ElementTree as ET
from pathlib import Path


class FeedValidator:
    """Валидатор YML фида для Prom.ua"""

    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_feed(self, feed_path):
        """Валидирует YML фид"""
        self.errors = []
        self.warnings = []

        try:
            tree = ET.parse(feed_path)
            root = tree.getroot()

            # Проверяем структуру
            self._validate_structure(root)

            # Проверяем offers
            offers = root.find('.//offers')
            if offers is not None:
                self._validate_offers(offers)

            # Проверяем категории
            categories = root.find('.//categories')
            if categories is not None:
                self._validate_categories(categories)

            return len(self.errors) == 0

        except ET.ParseError as e:
            self.errors.append(f"XML parsing error: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Validation error: {e}")
            return False

    def _validate_structure(self, root):
        """Проверяет основную структуру"""
        if root.tag != 'yml_catalog':
            self.errors.append("Root element must be 'yml_catalog'")

        shop = root.find('shop')
        if shop is None:
            self.errors.append("Missing 'shop' element")
            return

        required_elements = ['name', 'company', 'currencies', 'categories', 'offers']
        for element in required_elements:
            if shop.find(element) is None:
                self.errors.append(f"Missing required element: {element}")

    def _validate_offers(self, offers):
        """Проверяет offers"""
        offer_count = 0

        for offer in offers.findall('offer'):
            offer_count += 1
            offer_id = offer.get('id')

            if not offer_id:
                self.errors.append(f"Offer {offer_count} missing id attribute")

            # Проверяем обязательные поля
            required_fields = ['name', 'price', 'currencyId']
            for field in required_fields:
                if offer.find(field) is None:
                    self.errors.append(f"Offer {offer_id} missing required field: {field}")

            # Проверяем цену
            price_elem = offer.find('price')
            if price_elem is not None:
                try:
                    price = float(price_elem.text)
                    if price <= 0:
                        self.errors.append(f"Offer {offer_id} has invalid price: {price}")
                except ValueError:
                    self.errors.append(f"Offer {offer_id} has non-numeric price")

            # Проверяем изображения
            pictures = offer.findall('picture')
            if not pictures:
                self.warnings.append(f"Offer {offer_id} has no images")

    def _validate_categories(self, categories):
        """Проверяет категории"""
        category_ids = set()

        for category in categories.findall('category'):
            cat_id = category.get('id')

            if not cat_id:
                self.errors.append("Category missing id attribute")
                continue

            if cat_id in category_ids:
                self.errors.append(f"Duplicate category id: {cat_id}")

            category_ids.add(cat_id)

            if not category.text or not category.text.strip():
                self.errors.append(f"Category {cat_id} has empty name")

    def get_report(self):
        """Возвращает отчёт валидации"""
        report = []

        if self.errors:
            report.append("ERRORS:")
            for error in self.errors:
                report.append(f"  - {error}")

        if self.warnings:
            report.append("WARNINGS:")
            for warning in self.warnings:
                report.append(f"  - {warning}")

        if not self.errors and not self.warnings:
            report.append("Feed is valid!")

        return '\n'.join(report)
