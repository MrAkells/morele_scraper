# monitor_health.py
"""
Скрипт мониторинга здоровья парсера
"""

import requests
import sqlite3
import logging
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import Config


class HealthMonitor:
    """Мониторинг здоровья парсера"""

    def __init__(self, config_path="config.yaml"):
        self.config = Config(config_path)
        self.logger = self._setup_logger()
        self.alerts = []

    def _setup_logger(self):
        """Настройка логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("logs/health_monitor.log"),
                logging.StreamHandler(),
            ],
        )
        return logging.getLogger(__name__)

    def check_admin_panel(self):
        """Проверка работы админ-панели"""
        try:
            response = requests.get("http://localhost:5000", timeout=10)
            if response.status_code == 200:
                self.logger.info("✅ Admin panel is healthy")
                return True
            else:
                self.alerts.append(
                    f"Admin panel returned status {response.status_code}"
                )
                return False
        except Exception as e:
            self.alerts.append(f"Admin panel is not responding: {e}")
            return False

    def check_database(self):
        """Проверка состояния базы данных"""
        try:
            db_path = self.config.get("database.sqlite_path")

            if not Path(db_path).exists():
                self.alerts.append("Database file does not exist")
                return False

            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM products")
                product_count = cursor.fetchone()[0]

                cursor = conn.execute(
                    "SELECT COUNT(*) FROM categories WHERE is_active = 1"
                )
                active_categories = cursor.fetchone()[0]

                self.logger.info(
                    f"✅ Database healthy: {product_count} products, {active_categories} active categories"
                )

                if active_categories == 0:
                    self.alerts.append("No active categories found")

                return True

        except Exception as e:
            self.alerts.append(f"Database check failed: {e}")
            return False

    def check_recent_parsing(self, hours=25):
        """Проверка недавнего парсинга"""
        try:
            db_path = self.config.get("database.sqlite_path")
            cutoff_time = datetime.now() - timedelta(hours=hours)

            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM parsing_logs WHERE completed_at > ?",
                    (cutoff_time.isoformat(),),
                )
                recent_sessions = cursor.fetchone()[0]

                if recent_sessions > 0:
                    self.logger.info(
                        f"✅ Recent parsing activity: {recent_sessions} sessions in last {hours}h"
                    )
                    return True
                else:
                    self.alerts.append(f"No parsing activity in last {hours} hours")
                    return False

        except Exception as e:
            self.alerts.append(f"Parsing check failed: {e}")
            return False

    def check_disk_space(self, warning_threshold=80, critical_threshold=90):
        """Проверка свободного места на диске"""
        try:
            import shutil

            total, used, free = shutil.disk_usage("/")
            used_percent = (used / total) * 100

            if used_percent >= critical_threshold:
                self.alerts.append(f"CRITICAL: Disk usage {used_percent:.1f}%")
                return False
            elif used_percent >= warning_threshold:
                self.alerts.append(f"WARNING: Disk usage {used_percent:.1f}%")
                return True
            else:
                self.logger.info(f"✅ Disk usage: {used_percent:.1f}%")
                return True

        except Exception as e:
            self.alerts.append(f"Disk space check failed: {e}")
            return False

    def check_feed_freshness(self, hours=26):
        """Проверка актуальности фида"""
        try:
            feed_path = Path(self.config.get("feed.output_path", "feeds/prom_feed.yml"))

            if not feed_path.exists():
                self.alerts.append("Feed file does not exist")
                return False

            file_age = datetime.now() - datetime.fromtimestamp(
                feed_path.stat().st_mtime
            )

            if file_age.total_seconds() > hours * 3600:
                self.alerts.append(f"Feed is {file_age.days} days old")
                return False
            else:
                self.logger.info(
                    f"✅ Feed is fresh ({file_age.total_seconds() / 3600:.1f}h old)"
                )
                return True

        except Exception as e:
            self.alerts.append(f"Feed freshness check failed: {e}")
            return False

    def check_log_errors(self, hours=24):
        """Проверка ошибок в логах"""
        try:
            log_path = Path("logs/parser.log")

            if not log_path.exists():
                return True

            cutoff_time = datetime.now() - timedelta(hours=hours)
            error_count = 0

            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "ERROR" in line:
                        # Простая проверка времени в логе
                        try:
                            # Предполагаем формат: YYYY-MM-DD HH:MM:SS
                            time_str = line[:19]
                            log_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                            if log_time > cutoff_time:
                                error_count += 1
                        except:
                            continue

            if error_count > 10:
                self.alerts.append(
                    f"High error count in logs: {error_count} errors in last {hours}h"
                )
                return False
            elif error_count > 0:
                self.logger.info(f"⚠️ {error_count} errors in logs (last {hours}h)")
            else:
                self.logger.info(f"✅ No errors in logs (last {hours}h)")

            return True

        except Exception as e:
            self.alerts.append(f"Log check failed: {e}")
            return False

    def send_alerts(self):
        """Отправка уведомлений о проблемах"""
        if not self.alerts:
            return

        # Telegram уведомления
        if self.config.get("telegram.enabled"):
            self._send_telegram_alert()

        # Email уведомления (если настроены)
        email_config = self.config.get("email")
        if email_config and email_config.get("enabled"):
            self._send_email_alert()

        # Логирование всех алертов
        for alert in self.alerts:
            self.logger.error(f"ALERT: {alert}")

    def _send_telegram_alert(self):
        """Отправка в Telegram"""
        try:
            bot_token = self.config.get("telegram.bot_token")
            chat_id = self.config.get("telegram.chat_id")

            if not bot_token or not chat_id:
                return

            message = "🚨 Morele Parser Health Alert\n\n"
            message += "\n".join([f"• {alert}" for alert in self.alerts])
            message += f"\n\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}

            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                self.logger.info("Alert sent to Telegram")

        except Exception as e:
            self.logger.error(f"Failed to send Telegram alert: {e}")

    def _send_email_alert(self):
        """Отправка email уведомления"""
        try:
            email_config = self.config.get("email")

            msg = MIMEText("\n".join(self.alerts))
            msg["Subject"] = "Morele Parser Health Alert"
            msg["From"] = email_config["from"]
            msg["To"] = email_config["to"]

            with smtplib.SMTP(
                email_config["smtp_host"], email_config["smtp_port"]
            ) as server:
                if email_config.get("use_tls"):
                    server.starttls()

                if email_config.get("username"):
                    server.login(email_config["username"], email_config["password"])

                server.send_message(msg)

            self.logger.info("Alert sent via email")

        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")

    def run_health_check(self):
        """Запуск полной проверки здоровья"""
        self.logger.info("Starting health check...")

        checks = [
            self.check_admin_panel,
            self.check_database,
            self.check_recent_parsing,
            self.check_disk_space,
            self.check_feed_freshness,
            self.check_log_errors,
        ]

        results = []
        for check in checks:
            try:
                result = check()
                results.append(result)
            except Exception as e:
                self.logger.error(f"Health check failed: {e}")
                results.append(False)

        # Отправляем алерты если есть проблемы
        if self.alerts:
            self.send_alerts()

        # Возвращаем общий статус
        overall_health = all(results)

        if overall_health:
            self.logger.info("✅ All health checks passed")
        else:
            self.logger.error("❌ Some health checks failed")

        return overall_health


if __name__ == "__main__":
    # Основная функция для health monitor
    def main():
        monitor = HealthMonitor()

        import argparse

        parser = argparse.ArgumentParser(description="Morele Parser Health Monitor")
        parser.add_argument("--config", default="config.yaml", help="Config file path")
        parser.add_argument(
            "--check-only", action="store_true", help="Only check, do not send alerts"
        )

        args = parser.parse_args()

        monitor = HealthMonitor(args.config)

        if args.check_only:
            # Отключаем отправку алертов
            original_send = monitor.send_alerts
            monitor.send_alerts = lambda: None

        health_status = monitor.run_health_check()

        # Код выхода для использования в мониторинге
        sys.exit(0 if health_status else 1)

    if len(sys.argv) > 1 and sys.argv[1] == "health":
        main()
