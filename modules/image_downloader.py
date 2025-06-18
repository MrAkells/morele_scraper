# modules/image_downloader.py
"""
Модуль для загрузки изображений
"""

import os
import requests
import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image
import mimetypes


class ImageDownloader:
    """Загрузчик изображений"""

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)

        self.download_path = Path(config.get('images.download_path', 'images'))
        self.max_size_mb = config.get('images.max_size_mb', 10)
        self.allowed_formats = config.get('images.allowed_formats', ['jpg', 'jpeg', 'png', 'webp'])
        self.quality = config.get('images.quality', 85)

        # Создаём директорию для изображений
        self.download_path.mkdir(parents=True, exist_ok=True)

    def download_product_images(self, image_urls, product_id):
        """Загружает все изображения товара"""
        local_images = []

        # Создаём папку для товара
        product_dir = self.download_path / str(product_id)
        product_dir.mkdir(exist_ok=True)

        for i, url in enumerate(image_urls):
            try:
                local_path = self._download_image(url, product_dir, f"img_{i}")
                if local_path:
                    local_images.append(str(local_path))
            except Exception as e:
                self.logger.error(f"Failed to download image {url}: {e}")

        return local_images

    def _download_image(self, url, save_dir, filename_prefix):
        """Загружает одно изображение"""
        try:
            # Получаем изображение
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()

            # Проверяем размер
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.max_size_mb * 1024 * 1024:
                self.logger.warning(f"Image too large: {url}")
                return None

            # Определяем формат
            content_type = response.headers.get('content-type', '')
            extension = mimetypes.guess_extension(content_type)

            if not extension:
                # Пытаемся определить по URL
                parsed_url = urlparse(url)
                path_ext = Path(parsed_url.path).suffix.lower()
                if path_ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    extension = path_ext
                else:
                    extension = '.jpg'  # По умолчанию

            # Проверяем разрешённые форматы
            format_name = extension[1:].lower()
            if format_name not in self.allowed_formats:
                self.logger.warning(f"Unsupported format {format_name}: {url}")
                return None

            # Генерируем имя файла
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"{filename_prefix}_{url_hash}{extension}"
            filepath = save_dir / filename

            # Проверяем, не скачан ли уже файл
            if filepath.exists():
                return filepath

            # Сохраняем изображение
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Оптимизируем изображение
            self._optimize_image(filepath)

            self.logger.debug(f"Downloaded image: {filepath}")
            return filepath

        except Exception as e:
            self.logger.error(f"Error downloading image {url}: {e}")
            return None

    def _optimize_image(self, filepath):
        """Оптимизирует изображение"""
        try:
            with Image.open(filepath) as img:
                # Конвертируем в RGB если необходимо
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background

                # Ограничиваем размер
                max_size = (1200, 1200)
                if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)

                # Сохраняем с оптимизацией
                img.save(filepath, 'JPEG', quality=self.quality, optimize=True)

        except Exception as e:
            self.logger.error(f"Error optimizing image {filepath}: {e}")
