# cli_tools.py
"""
CLI инструменты для управления парсером
"""

import argparse
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent))

from utils.db_manager import DatabaseManager
from utils.monitor import SystemMonitor
from utils.image_optimizer import ImageOptimizer
from utils.feed_validator import FeedValidator
from config import Config


def backup_database(args):
    """Создаёт резервную копию БД"""
    config = Config()
    db_path = config.get('database.sqlite_path', 'data/morele_parser.db')

    manager = DatabaseManager(db_path)
    backup_file = manager.backup_database(args.backup_dir)
    print(f"Backup created: {backup_file}")


def cleanup_data(args):
    """Очищает старые данные"""
    config = Config()
    db_path = config.get('database.sqlite_path', 'data/morele_parser.db')

    manager = DatabaseManager(db_path)
    manager.cleanup_old_data(args.days)

    if args.optimize:
        manager.optimize_database()


def show_stats(args):
    """Показывает статистику"""
    config = Config()
    db_path = config.get('database.sqlite_path', 'data/morele_parser.db')

    # Статистика БД
    manager = DatabaseManager(db_path)
    db_stats = manager.get_database_stats()

    print("=== DATABASE STATISTICS ===")
    for key, value in db_stats.items():
        print(f"{key}: {value}")

    # Системная статистика
    if args.system:
        monitor = SystemMonitor()
        sys_stats = monitor.get_system_stats()

        print("\n=== SYSTEM STATISTICS ===")
        print(f"CPU Usage: {sys_stats['cpu_percent']}%")
        print(f"Memory Usage: {sys_stats['memory_percent']}%")
        print(f"Disk Usage: {sys_stats['disk_usage']}%")


def optimize_images(args):
    """Оптимизирует изображения"""
    optimizer = ImageOptimizer(quality=args.quality, max_size=(args.max_width, args.max_height))

    optimized, errors = optimizer.optimize_directory(
        args.directory,
        args.extensions.split(',') if args.extensions else None
    )

    print(f"Optimized: {optimized}, Errors: {errors}")


def validate_feed(args):
    """Валидирует YML фид"""
    validator = FeedValidator()

    if validator.validate_feed(args.feed_path):
        print("✅ Feed is valid!")
    else:
        print("❌ Feed has errors:")
        print(validator.get_report())


def monitor_system(args):
    """Мониторинг системы"""
    monitor = SystemMonitor()

    # Проверяем ресурсы
    disk_status, disk_msg = monitor.check_disk_space()
    memory_status, memory_msg = monitor.check_memory_usage()

    print(f"Disk: {disk_msg}")
    print(f"Memory: {memory_msg}")

    if disk_status == 'critical' or memory_status == 'critical':
        sys.exit(1)
    elif disk_status == 'warning' or memory_status == 'warning':
        sys.exit(2)


def main():
    """Главная функция CLI"""
    parser = argparse.ArgumentParser(description='Morele Parser CLI Tools')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create database backup')
    backup_parser.add_argument('--backup-dir', default='backups', help='Backup directory')
    backup_parser.set_defaults(func=backup_database)

    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Cleanup old data')
    cleanup_parser.add_argument('--days', type=int, default=30, help='Days to keep')
    cleanup_parser.add_argument('--optimize', action='store_true', help='Optimize database')
    cleanup_parser.set_defaults(func=cleanup_data)

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    stats_parser.add_argument('--system', action='store_true', help='Include system stats')
    stats_parser.set_defaults(func=show_stats)

    # Optimize images command
    images_parser = subparsers.add_parser('optimize-images', help='Optimize images')
    images_parser.add_argument('directory', help='Directory with images')
    images_parser.add_argument('--quality', type=int, default=85, help='JPEG quality')
    images_parser.add_argument('--max-width', type=int, default=1200, help='Max width')
    images_parser.add_argument('--max-height', type=int, default=1200, help='Max height')
    images_parser.add_argument('--extensions', help='File extensions (comma-separated)')
    images_parser.set_defaults(func=optimize_images)

    # Validate feed command
    validate_parser = subparsers.add_parser('validate-feed', help='Validate YML feed')
    validate_parser.add_argument('feed_path', help='Path to YML feed file')
    validate_parser.set_defaults(func=validate_feed)

    # Monitor command
    monitor_parser = subparsers.add_parser('monitor', help='Monitor system resources')
    monitor_parser.set_defaults(func=monitor_system)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        args.func(args)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
