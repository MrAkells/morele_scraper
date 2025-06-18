# modules/admin.py
"""
Простая веб-админка для управления парсером
"""

from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
import logging
from datetime import datetime, timedelta


class AdminPanel:
    """Простая веб-админка"""

    def __init__(self, config, storage):
        self.config = config
        self.storage = storage
        self.app = Flask(__name__)
        self.app.secret_key = 'morele-parser-secret-key'

        self._setup_routes()

    def _setup_routes(self):
        """Настройка маршрутов"""

        @self.app.route('/')
        def index():
            """Главная страница"""
            categories = self.storage.get_active_categories()
            stats = self.storage.get_parsing_stats(7)  # За неделю

            return render_template_string(self.INDEX_TEMPLATE,
                                        categories=categories,
                                        stats=stats)

        @self.app.route('/categories')
        def categories():
            """Страница управления категориями"""
            categories = self.storage.get_active_categories()
            return render_template_string(self.CATEGORIES_TEMPLATE, categories=categories)

        @self.app.route('/add_category', methods=['POST'])
        def add_category():
            """Добавление категории"""
            name = request.form.get('name')
            url = request.form.get('url')

            if name and url:
                try:
                    self.storage.add_category(name, url)
                    flash('Категория добавлена успешно', 'success')
                except Exception as e:
                    flash(f'Ошибка при добавлении категории: {e}', 'error')
            else:
                flash('Заполните все поля', 'error')

            return redirect(url_for('categories'))

        @self.app.route('/deactivate_category/<int:category_id>')
        def deactivate_category(category_id):
            """Деактивация категории"""
            try:
                self.storage.deactivate_category(category_id)
                flash('Категория деактивирована', 'success')
            except Exception as e:
                flash(f'Ошибка: {e}', 'error')

            return redirect(url_for('categories'))

        @self.app.route('/products')
        def products():
            """Страница товаров"""
            page = int(request.args.get('page', 1))
            per_page = 50

            # Здесь можно добавить пагинацию
            products = self.storage.get_products_for_feed()[:per_page]

            return render_template_string(self.PRODUCTS_TEMPLATE, products=products)

        @self.app.route('/api/stats')
        def api_stats():
            """API для получения статистики"""
            stats = self.storage.get_parsing_stats(30)
            return jsonify(stats)

    def run(self, host='127.0.0.1', port=5000):
        """Запуск админки"""
        self.app.run(host=host, port=port, debug=False)

    # HTML шаблоны
    INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Morele.net Parser - Админка</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .nav { margin-bottom: 20px; }
        .nav a { background: #007bff; color: white; padding: 10px 15px; text-decoration: none; margin-right: 10px; border-radius: 4px; }
        .nav a:hover { background: #0056b3; }
        .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .stat-item { text-align: center; padding: 20px; background: #f8f9fa; border-radius: 8px; }
        .stat-number { font-size: 2em; font-weight: bold; color: #007bff; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .status-active { color: #28a745; font-weight: bold; }
        .status-inactive { color: #dc3545; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Morele.net Parser - Админка</h1>
            <div class="nav">
                <a href="{{ url_for('index') }}">Главная</a>
                <a href="{{ url_for('categories') }}">Категории</a>
                <a href="{{ url_for('products') }}">Товары</a>
            </div>
        </div>

        <div class="card">
            <h2>📊 Статистика</h2>
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-number">{{ categories|length }}</div>
                    <div>Активных категорий</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{{ stats|length }}</div>
                    <div>Сессий парсинга за неделю</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>📋 Последние сессии парсинга</h2>
            {% if stats %}
            <table>
                <thead>
                    <tr>
                        <th>Дата</th>
                        <th>Категория</th>
                        <th>Найдено</th>
                        <th>Новых</th>
                        <th>Обновлено</th>
                        <th>Ошибок</th>
                    </tr>
                </thead>
                <tbody>
                    {% for stat in stats[:10] %}
                    <tr>
                        <td>{{ stat.completed_at }}</td>
                        <td>{{ stat.category_url }}</td>
                        <td>{{ stat.products_found }}</td>
                        <td>{{ stat.products_new }}</td>
                        <td>{{ stat.products_updated }}</td>
                        <td>{{ stat.errors_count }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p>Пока нет данных о парсинге</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
    '''

    CATEGORIES_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Категории - Morele.net Parser</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .nav { margin-bottom: 20px; }
        .nav a { background: #007bff; color: white; padding: 10px 15px; text-decoration: none; margin-right: 10px; border-radius: 4px; }
        .nav a:hover { background: #0056b3; }
        .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        .btn { background: #28a745; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #218838; }
        .btn-danger { background: #dc3545; }
        .btn-danger:hover { background: #c82333; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .alert { padding: 15px; margin-bottom: 20px; border-radius: 4px; }
        .alert-success { background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
        .alert-error { background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📁 Управление категориями</h1>
            <div class="nav">
                <a href="{{ url_for('index') }}">Главная</a>
                <a href="{{ url_for('categories') }}">Категории</a>
                <a href="{{ url_for('products') }}">Товары</a>
            </div>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="card">
            <h2>➕ Добавить категорию</h2>
            <form method="POST" action="{{ url_for('add_category') }}">
                <div class="form-group">
                    <label for="name">Название категории:</label>
                    <input type="text" id="name" name="name" required>
                </div>
                <div class="form-group">
                    <label for="url">URL категории на morele.net:</label>
                    <input type="url" id="url" name="url" required placeholder="https://www.morele.net/kategoria/...">
                </div>
                <button type="submit" class="btn">Добавить категорию</button>
            </form>
        </div>

        <div class="card">
            <h2>📋 Список категорий</h2>
            {% if categories %}
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Название</th>
                        <th>URL</th>
                        <th>Дата добавления</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody>
                    {% for category in categories %}
                    <tr>
                        <td>{{ category.id }}</td>
                        <td>{{ category.name }}</td>
                        <td><a href="{{ category.url }}" target="_blank">{{ category.url[:50] }}...</a></td>
                        <td>{{ category.created_at }}</td>
                        <td>
                            <a href="{{ url_for('deactivate_category', category_id=category.id) }}"
                               class="btn btn-danger"
                               onclick="return confirm('Уверены, что хотите деактивировать эту категорию?')">
                               Деактивировать
                            </a>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p>Пока нет добавленных категорий. Добавьте первую категорию выше.</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
    '''

    PRODUCTS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Товары - Morele.net Parser</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .nav { margin-bottom: 20px; }
        .nav a { background: #007bff; color: white; padding: 10px 15px; text-decoration: none; margin-right: 10px; border-radius: 4px; }
        .nav a:hover { background: #0056b3; }
        .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; font-size: 14px; }
        th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; position: sticky; top: 0; }
        .product-title { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .product-image { width: 50px; height: 50px; object-fit: cover; border-radius: 4px; }
        .price { font-weight: bold; color: #28a745; }
        .status-available { color: #28a745; }
        .status-unavailable { color: #dc3545; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📦 Товары</h1>
            <div class="nav">
                <a href="{{ url_for('index') }}">Главная</a>
                <a href="{{ url_for('categories') }}">Категории</a>
                <a href="{{ url_for('products') }}">Товары</a>
            </div>
        </div>

        <div class="card">
            <h2>📋 Список товаров</h2>
            {% if products %}
            <p>Показано товаров: {{ products|length }}</p>
            <table>
                <thead>
                    <tr>
                        <th>Изображение</th>
                        <th>Название (UA)</th>
                        <th>Цена (PLN)</th>
                        <th>Наличие</th>
                        <th>Категория</th>
                        <th>Обновлено</th>
                        <th>Ссылка</th>
                    </tr>
                </thead>
                <tbody>
                    {% for product in products %}
                    <tr>
                        <td>
                            {% if product.local_images %}
                                <img src="{{ product.local_images[0] }}" class="product-image" alt="Product image">
                            {% else %}
                                <div style="width: 50px; height: 50px; background: #f8f9fa; border-radius: 4px;"></div>
                            {% endif %}
                        </td>
                        <td class="product-title" title="{{ product.title_ua }}">{{ product.title_ua }}</td>
                        <td class="price">{{ "%.2f"|format(product.price) }} PLN</td>
                        <td class="{% if 'наличии' in product.availability %}status-available{% else %}status-unavailable{% endif %}">
                            {{ product.availability }}
                        </td>
                        <td>{{ product.category }}</td>
                        <td>{{ product.updated_at[:16] }}</td>
                        <td><a href="{{ product.url }}" target="_blank">Открыть</a></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <p>Пока нет товаров. Запустите парсинг для получения товаров.</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
    '''
