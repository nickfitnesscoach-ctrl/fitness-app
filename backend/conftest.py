"""
conftest.py — настройка pytest для Django.
"""

import os
import sys

# КРИТИЧНО: установить ДО того, как pytest-django загрузит Django
# Должно произойти при импорте conftest.py
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only"
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"

# Добавляем backend в sys.path если нужно
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
