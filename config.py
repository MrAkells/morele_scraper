# config.py
"""
Класс для работы с конфигурацией
"""

import yaml
import os
from pathlib import Path


class Config:
    """Класс для управления конфигурацией"""

    def __init__(self, config_path='config.yaml'):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self):
        """Загружает конфигурацию из YAML файла"""
        if not os.path.exists(self.config_path):
            self._create_default_config()

        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _create_default_config(self):
        """Создаёт конфигурационный файл по умолчанию"""
        default_config = {
            'database': {
                'type': 'sqlite',  # sqlite или mysql
                'sqlite_path': 'data/morele_parser.db',
                'mysql': {
                    'host': 'localhost',
                    'port': 3306,
                    'database': 'morele_parser',
                    'username': 'user',
                    'password': 'password'
                }
            },
            'parsing': {
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'delay_between_requests': 1,  # секунды
                'max_retries': 3,
                'timeout': 30,
                'concurrent_requests': 5
            },
            'images': {
                'download_path': 'images',
                'max_size_mb': 10,
                'allowed_formats': ['jpg', 'jpeg', 'png', 'webp'],
                'quality': 85
            },
            'translation': {
                'service': 'google',  # google, deepl, libretranslate
                'cache_enabled': True,
                'cache_path': 'data/translation_cache.db',
                'google': {
                    'api_key': '',  # Заполнить
                    'source_lang': 'pl',
                    'target_lang': 'uk'
                },
                'deepl': {
                    'api_key': '',
                    'source_lang': 'PL',
                    'target_lang': 'UK'
                },
                'libretranslate': {
                    'url': 'https://libretranslate.de',
                    'api_key': ''
                }
            },
            'feed': {
                'output_path': 'feeds/prom_feed.yml',
                'shop_name': 'Ваш магазин',
                'company': 'Ваша компания',
                'currency': 'UAH',
                'pln_to_uah_rate': 'auto',  # auto или число
                'margin_percent': 10,  # наценка в процентах
                'categories_mapping': {}  # соответствие категорий morele и prom
            },
            'telegram': {
                'enabled': False,
                'bot_token': '',
                'chat_id': ''
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/parser.log',
                'max_size_mb': 50,
                'backup_count': 5
            }
        }

        # Создаём директорию для конфига если её нет
        Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)

        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)

        return default_config

    def get(self, key, default=None):
        """Получает значение из конфигурации по ключу (поддерживает точечную нотацию)"""
        keys = key.split('.')
        value = self.config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key, value):
        """Устанавливает значение в конфигурации"""
        keys = key.split('.')
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value
        self.save()

    def save(self):
        """Сохраняет конфигурацию в файл"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
