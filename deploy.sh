#!/bin/bash
# Скрипт для развертывания парсера

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="/opt/morele_parser"
SERVICE_USER="morele"
PYTHON_VERSION="3.11"

echo "🚀 Deploying Morele Parser..."

# Функция для вывода сообщений
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Проверка прав root
if [[ $EUID -eq 0 ]]; then
    echo "❌ Don't run this script as root"
    exit 1
fi

# Установка системных зависимостей
install_system_deps() {
    log "Installing system dependencies..."

    sudo apt update
    sudo apt install -y \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-venv \
        python${PYTHON_VERSION}-dev \
        nginx \
        sqlite3 \
        supervisor \
        curl \
        wget \
        unzip \
        git
}

# Создание пользователя
create_user() {
    if ! id "$SERVICE_USER" &>/dev/null; then
        log "Creating user $SERVICE_USER..."
        sudo useradd -r -s /bin/bash -d $PROJECT_DIR $SERVICE_USER
    fi
}

# Создание директорий
create_directories() {
    log "Creating directories..."

    sudo mkdir -p $PROJECT_DIR
    sudo mkdir -p $PROJECT_DIR/{data,images,feeds,logs,backups}
    sudo mkdir -p /var/log/morele_parser

    sudo chown -R $SERVICE_USER:$SERVICE_USER $PROJECT_DIR
    sudo chown -R $SERVICE_USER:$SERVICE_USER /var/log/morele_parser
}

# Копирование файлов
copy_files() {
    log "Copying files..."

    sudo cp -r $SCRIPT_DIR/* $PROJECT_DIR/
    sudo chown -R $SERVICE_USER:$SERVICE_USER $PROJECT_DIR
}

# Создание виртуального окружения
setup_venv() {
    log "Setting up Python virtual environment..."

    sudo -u $SERVICE_USER python${PYTHON_VERSION} -m venv $PROJECT_DIR/venv
    sudo -u $SERVICE_USER $PROJECT_DIR/venv/bin/pip install --upgrade pip
    sudo -u $SERVICE_USER $PROJECT_DIR/venv/bin/pip install -r $PROJECT_DIR/requirements.txt
}

# Настройка конфигурации
setup_config() {
    log "Setting up configuration..."

    if [ ! -f "$PROJECT_DIR/config.yaml" ]; then
        sudo -u $SERVICE_USER $PROJECT_DIR/venv/bin/python $PROJECT_DIR/main.py --help > /dev/null
        log "Default config created. Please edit $PROJECT_DIR/config.yaml"
    fi
}

# Настройка Supervisor
setup_supervisor() {
    log "Setting up Supervisor..."

    sudo tee /etc/supervisor/conf.d/morele_parser.conf > /dev/null <<EOF
[program:morele_parser_admin]
command=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/main.py --admin --host 127.0.0.1 --port 5000
directory=$PROJECT_DIR
user=$SERVICE_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/morele_parser/admin.log
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=3
environment=PYTHONPATH="$PROJECT_DIR"

[program:morele_parser_monitor]
command=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/cli_tools.py monitor
directory=$PROJECT_DIR
user=$SERVICE_USER
autostart=false
autorestart=false
startsecs=0
redirect_stderr=true
stdout_logfile=/var/log/morele_parser/monitor.log
EOF

    sudo supervisorctl reread
    sudo supervisorctl update
}

# Настройка Nginx
setup_nginx() {
    log "Setting up Nginx..."

    # Резервная копия существующей конфигурации
    if [ -f "/etc/nginx/sites-available/default" ]; then
        sudo cp /etc/nginx/sites-available/default /etc/nginx/sites-available/default.backup
    fi

    # Создание конфигурации для парсера
    sudo tee /etc/nginx/sites-available/morele_parser > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    client_max_body_size 50M;

    # Раздача изображений
    location /images/ {
        alias $PROJECT_DIR/images/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Раздача фидов
    location /feeds/ {
        alias $PROJECT_DIR/feeds/;
        add_header Access-Control-Allow-Origin "*";
    }

    # Админка
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
EOF

    # Активация сайта
    sudo ln -sf /etc/nginx/sites-available/morele_parser /etc/nginx/sites-enabled/
    sudo rm -f /etc/nginx/sites-enabled/default

    # Проверка конфигурации
    sudo nginx -t
}

# Настройка cron
setup_cron() {
    log "Setting up cron jobs..."

    sudo -u $SERVICE_USER crontab -l > /tmp/morele_cron 2>/dev/null || true

    cat >> /tmp/morele_cron <<EOF
# Morele Parser Jobs
0 2 * * * cd $PROJECT_DIR && $PROJECT_DIR/venv/bin/python main.py --parse >> logs/cron.log 2>&1
0 3 * * * cd $PROJECT_DIR && $PROJECT_DIR/venv/bin/python main.py --generate-feed >> logs/cron.log 2>&1
0 4 * * 0 cd $PROJECT_DIR && $PROJECT_DIR/venv/bin/python cli_tools.py backup --backup-dir backups >> logs/cron.log 2>&1
0 5 * * 0 cd $PROJECT_DIR && $PROJECT_DIR/venv/bin/python cli_tools.py cleanup --days 30 --optimize >> logs/cron.log 2>&1
EOF

    sudo -u $SERVICE_USER crontab /tmp/morele_cron
    rm /tmp/morele_cron
}

# Настройка логротации
setup_logrotate() {
    log "Setting up log rotation..."

    sudo tee /etc/logrotate.d/morele_parser > /dev/null <<EOF
$PROJECT_DIR/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
    su $SERVICE_USER $SERVICE_USER
}

/var/log/morele_parser/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    copytruncate
    postrotate
        supervisorctl restart morele_parser_admin
    endscript
}
EOF
}

# Запуск сервисов
start_services() {
    log "Starting services..."

    sudo systemctl enable supervisor
    sudo systemctl start supervisor

    sudo systemctl enable nginx
    sudo systemctl restart nginx

    sudo supervisorctl start morele_parser_admin
}

# Проверка установки
verify_installation() {
    log "Verifying installation..."

    # Проверка админки
    if curl -s http://localhost:5000 > /dev/null; then
        log "✅ Admin panel is running"
    else
        log "❌ Admin panel is not responding"
    fi

    # Проверка nginx
    if curl -s http://localhost/health | grep -q "healthy"; then
        log "✅ Nginx is working"
    else
        log "❌ Nginx is not working"
    fi

    # Проверка supervisor
    if sudo supervisorctl status morele_parser_admin | grep -q "RUNNING"; then
        log "✅ Supervisor service is running"
    else
        log "❌ Supervisor service is not running"
    fi
}

# Основная функция
main() {
    log "Starting deployment process..."

    install_system_deps
    create_user
    create_directories
    copy_files
    setup_venv
    setup_config
    setup_supervisor
    setup_nginx
    setup_cron
    setup_logrotate
    start_services
    verify_installation

    log "🎉 Deployment completed!"
    log "Admin panel: http://your-server-ip/"
    log "Please edit configuration: $PROJECT_DIR/config.yaml"
    log "Check logs: tail -f /var/log/morele_parser/admin.log"
}

# Проверка аргументов
case "${1:-}" in
    "install")
        main
        ;;
    "update")
        copy_files
        sudo supervisorctl restart morele_parser_admin
        log "Updated successfully"
        ;;
    "status")
        sudo supervisorctl status
        sudo systemctl status nginx
        ;;
    "logs")
        tail -f /var/log/morele_parser/admin.log
        ;;
    *)
        echo "Usage: $0 {install|update|status|logs}"
        echo "  install - Full installation"
        echo "  update  - Update code only"
        echo "  status  - Show service status"
        echo "  logs    - Show logs"
        exit 1
        ;;
esac

# ===== update.sh =====
#!/bin/bash
# Скрипт для обновления парсера

set -e

PROJECT_DIR="/opt/morele_parser"
SERVICE_USER="morele"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Создание резервной копии
backup_current() {
    log "Creating backup..."

    BACKUP_DIR="$PROJECT_DIR/backups/update_$(date +%Y%m%d_%H%M%S)"
    sudo -u $SERVICE_USER mkdir -p "$BACKUP_DIR"

    sudo -u $SERVICE_USER cp -r $PROJECT_DIR/{*.py,modules,config.yaml} "$BACKUP_DIR/" 2>/dev/null || true
    sudo -u $SERVICE_USER $PROJECT_DIR/venv/bin/python $PROJECT_DIR/cli_tools.py backup --backup-dir "$BACKUP_DIR"

    log "Backup created: $BACKUP_DIR"
}

# Обновление кода
update_code() {
    log "Updating code..."

    # Здесь можно добавить git pull или копирование новых файлов
    # git -C $PROJECT_DIR pull origin main

    # Или копирование из source директории
    if [ -d "./source" ]; then
        sudo cp -r ./source/* $PROJECT_DIR/
        sudo chown -R $SERVICE_USER:$SERVICE_USER $PROJECT_DIR
    fi
}

# Обновление зависимостей
update_dependencies() {
    log "Updating dependencies..."

    sudo -u $SERVICE_USER $PROJECT_DIR/venv/bin/pip install --upgrade pip
    sudo -u $SERVICE_USER $PROJECT_DIR/venv/bin/pip install -r $PROJECT_DIR/requirements.txt --upgrade
}

# Миграция базы данных (если нужно)
migrate_database() {
    log "Checking database migrations..."

    # Здесь можно добавить скрипты миграции БД
    # sudo -u $SERVICE_USER $PROJECT_DIR/venv/bin/python $PROJECT_DIR/migrate.py
}

# Перезапуск сервисов
restart_services() {
    log "Restarting services..."

    sudo supervisorctl restart morele_parser_admin
    sudo systemctl reload nginx
}

# Проверка обновления
verify_update() {
    log "Verifying update..."

    sleep 5

    if curl -s http://localhost:5000 > /dev/null; then
        log "✅ Update successful"
    else
        log "❌ Update failed, check logs"
        sudo supervisorctl status
        exit 1
    fi
}

main() {
    log "Starting update process..."

    backup_current
    update_code
    update_dependencies
    migrate_database
    restart_services
    verify_update

    log "🎉 Update completed successfully!"
}

main
