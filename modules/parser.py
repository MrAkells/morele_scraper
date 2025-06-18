# modules/parser.py
"""
Модуль для парсинга товаров с morele.net
"""

import requests
import time
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed


class MoreleParser:
    """Парсер для morele.net"""

    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.logger = logging.getLogger(__name__)

        # Настройка сессии
        self.session.headers.update({
            'User-Agent': config.get('parsing.user_agent'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pl,en-US;q=0.7,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

    def parse_category(self, category_url):
        """Парсит все товары из категории"""
        self.logger.info(f"Начинаем парсинг категории: {category_url}")

        products = []
        page = 1
        max_pages = self.config.get('parsing.max_pages', 100)

        while page <= max_pages:
            self.logger.debug(f"Парсинг страницы {page}")

            page_url = self._get_page_url(category_url, page)
            page_products = self._parse_category_page(page_url)

            if not page_products:
                self.logger.info(f"Страница {page} пуста, завершаем парсинг категории")
                break

            products.extend(page_products)
            page += 1

            # Пауза между запросами
            time.sleep(self.config.get('parsing.delay_between_requests', 1))

        self.logger.info(f"Найдено {len(products)} товаров в категории")
        return products

    def _get_page_url(self, base_url, page):
        """Формирует URL для конкретной страницы"""
        if page == 1:
            return base_url

        # Проверяем, есть ли уже параметры в URL
        separator = '&' if '?' in base_url else '?'
        return f"{base_url}{separator}page={page}"

    def _parse_category_page(self, page_url):
        """Парсит товары с одной страницы категории"""
        try:
            response = self._make_request(page_url)
            if not response:
                return []

            soup = BeautifulSoup(response.content, 'html.parser')

            # Ищем карточки товаров
            product_cards = soup.find_all('div', class_='cat-product')
            products = []

            # Используем многопоточность для парсинга товаров
            with ThreadPoolExecutor(max_workers=self.config.get('parsing.concurrent_requests', 5)) as executor:
                futures = []

                for card in product_cards:
                    product_url = self._extract_product_url(card)
                    if product_url:
                        future = executor.submit(self._parse_product_page, product_url)
                        futures.append(future)

                for future in as_completed(futures):
                    try:
                        product = future.result()
                        if product:
                            products.append(product)
                    except Exception as e:
                        self.logger.error(f"Ошибка при парсинге товара: {e}")

            return products

        except Exception as e:
            self.logger.error(f"Ошибка при парсинге страницы {page_url}: {e}")
            return []

    def _extract_product_url(self, card):
        """Извлекает URL товара из карточки"""
        try:
            link = card.find('a', href=True)
            if link:
                href = link['href']
                if not href.startswith('http'):
                    href = urljoin('https://www.morele.net', href)
                return href
        except Exception as e:
            self.logger.error(f"Ошибка при извлечении URL товара: {e}")

        return None

    def _parse_product_page(self, product_url):
        """Парсит детальную страницу товара"""
        try:
            response = self._make_request(product_url)
            if not response:
                return None

            soup = BeautifulSoup(response.content, 'html.parser')

            # Извлекаем данные товара
            product = {
                'url': product_url,
                'id': self._extract_product_id(product_url),
                'title': self._extract_title(soup),
                'price': self._extract_price(soup),
                'availability': self._extract_availability(soup),
                'description': self._extract_description(soup),
                'attributes': self._extract_attributes(soup),
                'category': self._extract_category(soup),
                'images': self._extract_images(soup),
                'brand': self._extract_brand(soup),
                'model': self._extract_model(soup),
                'sku': self._extract_sku(soup),
                'parsed_at': time.time()
            }

            # Генерируем хеш для определения изменений
            product['content_hash'] = self._generate_content_hash(product)

            return product

        except Exception as e:
            self.logger.error(f"Ошибка при парсинге товара {product_url}: {e}")
            return None

    def _extract_product_id(self, url):
        """Извлекает ID товара из URL"""
        # Ищем числовой ID в URL
        match = re.search(r'/(\d+)-', url)
        if match:
            return match.group(1)

        # Если не найден, используем хеш URL
        return hashlib.md5(url.encode()).hexdigest()[:10]

    def _extract_title(self, soup):
        """Извлекает название товара"""
        selectors = [
            'h1.prod-name',
            'h1[data-test="product-name"]',
            'h1.product-title',
            '.product-name h1',
            'h1'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)

        return "Без названия"

    def _extract_price(self, soup):
        """Извлекает цену товара"""
        selectors = [
            '.price-new',
            '.price-main',
            '[data-test="product-price"]',
            '.product-price .price',
            '.price'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                # Извлекаем числовое значение
                price_match = re.search(r'([\d\s]+[,.]?\d*)', price_text.replace(' ', ''))
                if price_match:
                    price_str = price_match.group(1).replace(' ', '').replace(',', '.')
                    try:
                        return float(price_str)
                    except ValueError:
                        continue

        return 0.0

    def _extract_availability(self, soup):
        """Извлекает информацию о наличии"""
        selectors = [
            '.availability',
            '[data-test="product-availability"]',
            '.product-availability',
            '.stock-info'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                availability_text = element.get_text(strip=True).lower()

                if any(word in availability_text for word in ['dostępny', 'w magazynie', 'dostępne']):
                    return 'в наличии'
                elif any(word in availability_text for word in ['brak', 'niedostępny']):
                    return 'нет в наличии'
                else:
                    return availability_text

        return 'неизвестно'

    def _extract_description(self, soup):
        """Извлекает описание товара"""
        selectors = [
            '.product-description',
            '[data-test="product-description"]',
            '.prod-description',
            '.description',
            '.product-details .description'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                # Удаляем HTML теги и лишние пробелы
                description = element.get_text(separator=' ', strip=True)
                return re.sub(r'\s+', ' ', description)

        return ""

    def _extract_attributes(self, soup):
        """Извлекает характеристики товара"""
        attributes = {}

        # Различные селекторы для характеристик
        specs_sections = soup.find_all(['div', 'section'], class_=re.compile(r'spec|param|attribute|feature'))

        for section in specs_sections:
            # Ищем пары ключ-значение
            rows = section.find_all(['tr', 'div'], class_=re.compile(r'spec-row|param-row|attribute-row'))

            for row in rows:
                # Пытаемся найти название и значение
                name_elem = row.find(['td', 'div', 'span'], class_=re.compile(r'name|key|label'))
                value_elem = row.find(['td', 'div', 'span'], class_=re.compile(r'value|val'))

                if name_elem and value_elem:
                    name = name_elem.get_text(strip=True)
                    value = value_elem.get_text(strip=True)

                    if name and value and len(name) < 100:
                        attributes[name] = value

        return attributes

    def _extract_category(self, soup):
        """Извлекает категорию товара"""
        # Ищем хлебные крошки
        breadcrumb_selectors = [
            '.breadcrumb',
            '.breadcrumbs',
            '[data-test="breadcrumb"]',
            '.navigation-path'
        ]

        for selector in breadcrumb_selectors:
            breadcrumb = soup.select_one(selector)
            if breadcrumb:
                links = breadcrumb.find_all('a')
                if len(links) > 1:  # Пропускаем "Главная"
                    return links[-1].get_text(strip=True)

        return "Без категории"

    def _extract_images(self, soup):
        """Извлекает изображения товара"""
        images = []

        # Селекторы для изображений
        img_selectors = [
            '.product-gallery img',
            '.product-images img',
            '[data-test="product-image"]',
            '.gallery img',
            '.product-photo img'
        ]

        for selector in img_selectors:
            imgs = soup.select(selector)
            for img in imgs:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                if src:
                    if not src.startswith('http'):
                        src = urljoin('https://www.morele.net', src)

                    # Фильтруем маленькие изображения
                    if not any(size in src for size in ['icon', 'thumb', 'small']) and src not in images:
                        images.append(src)

        return images[:10]  # Ограничиваем количество изображений

    def _extract_brand(self, soup):
        """Извлекает бренд товара"""
        selectors = [
            '[data-test="product-brand"]',
            '.product-brand',
            '.brand',
            '.manufacturer'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)

        return ""

    def _extract_model(self, soup):
        """Извлекает модель товара"""
        selectors = [
            '[data-test="product-model"]',
            '.product-model',
            '.model'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)

        return ""

    def _extract_sku(self, soup):
        """Извлекает артикул товара"""
        selectors = [
            '[data-test="product-sku"]',
            '.product-sku',
            '.sku',
            '.article-number',
            '.product-code'
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)

        return ""

    def _generate_content_hash(self, product):
        """Генерирует хеш содержимого товара для определения изменений"""
        content = f"{product['title']}{product['price']}{product['availability']}{product['description']}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def _make_request(self, url, retries=None):
        """Выполняет HTTP запрос с повторными попытками"""
        if retries is None:
            retries = self.config.get('parsing.max_retries', 3)

        for attempt in range(retries + 1):
            try:
                response = self.session.get(
                    url,
                    timeout=self.config.get('parsing.timeout', 30)
                )

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Too Many Requests
                    wait_time = (attempt + 1) * 5
                    self.logger.warning(f"Rate limit hit, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    self.logger.warning(f"HTTP {response.status_code} for {url}")

            except requests.RequestException as e:
                self.logger.error(f"Request error on attempt {attempt + 1} for {url}: {e}")

                if attempt < retries:
                    time.sleep((attempt + 1) * 2)

        self.logger.error(f"Failed to fetch {url} after {retries + 1} attempts")
        return None
