# utils/monitor.py
"""
Система мониторинга парсера
"""

import psutil
import time
import json
from datetime import datetime
from pathlib import Path


class SystemMonitor:
    """Мониторинг системных ресурсов"""

    def __init__(self, log_file='logs/monitoring.log'):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(exist_ok=True)

    def get_system_stats(self):
        """Получает статистику системы"""
        stats = {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'network_io': dict(psutil.net_io_counters()._asdict()) if hasattr(psutil, 'net_io_counters') else {},
            'process_count': len(psutil.pids())
        }

        return stats

    def log_stats(self):
        """Записывает статистику в лог"""
        stats = self.get_system_stats()

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(stats, ensure_ascii=False) + '\n')

    def check_disk_space(self, warning_threshold=80, critical_threshold=90):
        """Проверяет свободное место на диске"""
        disk_usage = psutil.disk_usage('/').percent

        if disk_usage >= critical_threshold:
            return 'critical', f"Критически мало места на диске: {disk_usage}%"
        elif disk_usage >= warning_threshold:
            return 'warning', f"Мало места на диске: {disk_usage}%"
        else:
            return 'ok', f"Место на диске: {disk_usage}%"

    def check_memory_usage(self, warning_threshold=80, critical_threshold=90):
        """Проверяет использование памяти"""
        memory_usage = psutil.virtual_memory().percent

        if memory_usage >= critical_threshold:
            return 'critical', f"Критически высокое использование памяти: {memory_usage}%"
        elif memory_usage >= warning_threshold:
            return 'warning', f"Высокое использование памяти: {memory_usage}%"
        else:
            return 'ok', f"Использование памяти: {memory_usage}%"
