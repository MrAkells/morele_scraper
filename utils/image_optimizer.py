# utils/image_optimizer.py
"""
Утилиты для оптимизации изображений
"""

from PIL import Image
import os
from pathlib import Path
import logging


class ImageOptimizer:
    """Оптимизатор изображений"""

    def __init__(self, quality=85, max_size=(1200, 1200)):
        self.quality = quality
        self.max_size = max_size
        self.logger = logging.getLogger(__name__)

    def optimize_image(self, image_path, output_path=None):
        """Оптимизирует одно изображение"""
        if output_path is None:
            output_path = image_path

        try:
            with Image.open(image_path) as img:
                # Конвертируем в RGB если нужно
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode in ('RGBA', 'LA'):
                        background.paste(img, mask=img.split()[-1])
                        img = background

                # Изменяем размер если нужно
                if img.size[0] > self.max_size[0] or img.size[1] > self.max_size[1]:
                    img.thumbnail(self.max_size, Image.Resampling.LANCZOS)

                # Сохраняем с оптимизацией
                img.save(output_path, 'JPEG', quality=self.quality, optimize=True)

                return True

        except Exception as e:
            self.logger.error(f"Error optimizing image {image_path}: {e}")
            return False

    def optimize_directory(self, directory_path, extensions=None):
        """Оптимизирует все изображения в директории"""
        if extensions is None:
            extensions = ['.jpg', '.jpeg', '.png', '.webp']

        directory = Path(directory_path)
        optimized_count = 0
        error_count = 0

        for file_path in directory.rglob('*'):
            if file_path.suffix.lower() in extensions:
                if self.optimize_image(file_path):
                    optimized_count += 1
                else:
                    error_count += 1

        print(f"Optimized {optimized_count} images, {error_count} errors")
        return optimized_count, error_count
