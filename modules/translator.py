# modules/translator.py
"""
Модуль для перевода текста с кешем
"""

import hashlib
import logging
import time
from abc import ABC, abstractmethod


class TranslationProvider(ABC):
    """Абстрактный класс для провайдеров перевода"""

    @abstractmethod
    def translate(self, text, source_lang, target_lang):
        pass


class GoogleTranslateProvider(TranslationProvider):
    """Провайдер Google Translate"""

    def __init__(self, api_key):
        self.api_key = api_key

    def translate(self, text, source_lang='pl', target_lang='uk'):
        try:
            from googletrans import Translator
            translator = Translator()
            result = translator.translate(text, src=source_lang, dest=target_lang)
            return result.text
        except Exception as e:
            logging.error(f"Google Translate error: {e}")
            raise


class DeepLProvider(TranslationProvider):
    """Провайдер DeepL"""

    def __init__(self, api_key):
        self.api_key = api_key

    def translate(self, text, source_lang='PL', target_lang='UK'):
        try:
            import deepl
            translator = deepl.Translator(self.api_key)
            result = translator.translate_text(text, source_lang=source_lang, target_lang=target_lang)
            return result.text
        except Exception as e:
            logging.error(f"DeepL error: {e}")
            raise


class LibreTranslateProvider(TranslationProvider):
    """Провайдер LibreTranslate"""

    def __init__(self, url, api_key=None):
        self.url = url
        self.api_key = api_key

    def translate(self, text, source_lang='pl', target_lang='uk'):
        try:
            import requests

            data = {
                'q': text,
                'source': source_lang,
                'target': target_lang,
                'format': 'text'
            }

            if self.api_key:
                data['api_key'] = self.api_key

            response = requests.post(f"{self.url}/translate", data=data)
            response.raise_for_status()

            return response.json()['translatedText']
        except Exception as e:
            logging.error(f"LibreTranslate error: {e}")
            raise


class TranslationService:
    """Сервис для перевода с кешем"""

    def __init__(self, config, storage):
        self.config = config
        self.storage = storage
        self.logger = logging.getLogger(__name__)

        # Инициализация провайдера
        self.provider = self._init_provider()

        # Настройки
        self.cache_enabled = config.get('translation.cache_enabled', True)
        self.source_lang = config.get('translation.google.source_lang', 'pl')
        self.target_lang = config.get('translation.google.target_lang', 'uk')

    def _init_provider(self):
        """Инициализирует провайдера перевода"""
        service = self.config.get('translation.service', 'google')

        if service == 'google':
            api_key = self.config.get('translation.google.api_key')
            if not api_key:
                self.logger.warning("Google Translate API key not found, using googletrans library")
            return GoogleTranslateProvider(api_key)

        elif service == 'deepl':
            api_key = self.config.get('translation.deepl.api_key')
            if not api_key:
                raise ValueError("DeepL API key is required")
            return DeepLProvider(api_key)

        elif service == 'libretranslate':
            url = self.config.get('translation.libretranslate.url')
            api_key = self.config.get('translation.libretranslate.api_key')
            return LibreTranslateProvider(url, api_key)

        else:
            raise ValueError(f"Unsupported translation service: {service}")

    def translate(self, text):
        """Переводит текст с использованием кеша"""
        if not text or not text.strip():
            return text

        text = text.strip()

        # Проверяем кеш
        if self.cache_enabled:
            cached = self.storage.get_translation_from_cache(text)
            if cached:
                return cached

        try:
            # Переводим
            translated = self.provider.translate(text, self.source_lang, self.target_lang)

            # Сохраняем в кеш
            if self.cache_enabled and translated:
                self.storage.save_translation_to_cache(text, translated)

            # Небольшая пауза чтобы не превысить лимиты API
            time.sleep(0.1)

            return translated

        except Exception as e:
            self.logger.error(f"Translation failed for text '{text[:50]}...': {e}")
            return text  # Возвращаем оригинальный текст при ошибке


