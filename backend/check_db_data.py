#!/usr/bin/env python
"""
Diagnostic script to check database data for FoodMind project.
Run: python check_db_data.py
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.contrib.auth.models import User
from apps.telegram.models import TelegramUser
from apps.users.models import Profile
from apps.nutrition.models import Meal, FoodItem, DailyGoal

def print_header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def check_telegram_users():
    print_header("TELEGRAM USERS (заявки и клиенты)")

    total = TelegramUser.objects.count()
    completed_test = TelegramUser.objects.filter(ai_test_completed=True).count()
    clients = TelegramUser.objects.filter(is_client=True).count()

    print(f"Всего Telegram пользователей: {total}")
    print(f"Прошли AI тест (заявки): {completed_test}")
    print(f"Добавлены в клиенты: {clients}")

    if completed_test > 0:
        print("\nПоследние 5 заявок:")
        for user in TelegramUser.objects.filter(ai_test_completed=True).order_by('-created_at')[:5]:
            print(f"  - {user.display_name} (ID: {user.telegram_id}) - {user.created_at.strftime('%Y-%m-%d %H:%M')}")
            if user.recommended_calories:
                print(f"    КБЖУ: {user.recommended_calories} ккал / {user.recommended_protein}г Б / {user.recommended_fat}г Ж / {user.recommended_carbs}г У")
    else:
        print("\n⚠️  НЕТ ЗАЯВОК! Проверьте:")
        print("   1. Бот отправляет данные в Django? (DJANGO_API_URL настроен?)")
        print("   2. Backend использует PostgreSQL? (не SQLite)")
        print("   3. Логи бота: docker logs fm-bot | grep 'Test results saved'")

def check_users_and_profiles():
    print_header("DJANGO USERS & PROFILES")

    total_users = User.objects.count()
    profiles_with_data = Profile.objects.exclude(weight__isnull=True).count()

    print(f"Всего Django пользователей: {total_users}")
    print(f"Профили с заполненными данными: {profiles_with_data}")

    if profiles_with_data > 0:
        print("\nПоследние 5 профилей:")
        for profile in Profile.objects.exclude(weight__isnull=True).order_by('-id')[:5]:
            print(f"  - {profile.user.username} | Вес: {profile.weight}кг, Рост: {profile.height}см, Цель: {profile.goal_type}")

def check_meals():
    print_header("ПРИЁМЫ ПИЩИ (миниапп)")

    total_meals = Meal.objects.count()
    total_items = FoodItem.objects.count()

    print(f"Всего приёмов пищи: {total_meals}")
    print(f"Всего блюд (food items): {total_items}")

    if total_meals > 0:
        print("\nПоследние 5 приёмов пищи:")
        for meal in Meal.objects.order_by('-created_at')[:5]:
            items_count = meal.items.count()
            total_cals = sum(item.calories for item in meal.items.all())
            print(f"  - {meal.user.username} | {meal.get_meal_type_display()} | {meal.date} | {items_count} блюд | {total_cals:.0f} ккал")
    else:
        print("\n⚠️  НЕТ ПРИЁМОВ ПИЩИ! Проверьте:")
        print("   1. Клиентский миниапп работает через Telegram WebApp?")
        print("   2. AI API настроен? (OPENROUTER_API_KEY)")
        print("   3. Логи backend: docker logs fm-backend | grep 'POST /api/v1/meals'")

def check_goals():
    print_header("DAILY GOALS (КБЖУ цели)")

    total_goals = DailyGoal.objects.count()
    active_goals = DailyGoal.objects.filter(is_active=True).count()

    print(f"Всего целей КБЖУ: {total_goals}")
    print(f"Активных целей: {active_goals}")

    if active_goals > 0:
        print("\nПоследние 5 активных целей:")
        for goal in DailyGoal.objects.filter(is_active=True).order_by('-created_at')[:5]:
            print(f"  - {goal.user.username} | {goal.calories} ккал / {goal.protein}г Б / {goal.fat}г Ж / {goal.carbohydrates}г У | Источник: {goal.source}")

def check_database_connection():
    print_header("DATABASE CONNECTION")

    from django.conf import settings
    from django.db import connection

    db_config = settings.DATABASES['default']
    print(f"Engine: {db_config['ENGINE']}")

    if 'sqlite' in db_config['ENGINE']:
        print("⚠️  WARNING: Используется SQLite!")
        print("   Измените backend/.env → DATABASE_URL=postgresql://...")
    else:
        print(f"✓ Используется PostgreSQL")
        print(f"  Host: {db_config.get('HOST', 'N/A')}")
        print(f"  Name: {db_config.get('NAME', 'N/A')}")
        print(f"  User: {db_config.get('USER', 'N/A')}")

    # Test connection
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("✓ Подключение к БД успешно")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

def main():
    print("\n" + "=" * 70)
    print("  FoodMind Database Diagnostic Tool")
    print("=" * 70)

    check_database_connection()
    check_telegram_users()
    check_users_and_profiles()
    check_meals()
    check_goals()

    print("\n" + "=" * 70)
    print("  Диагностика завершена")
    print("=" * 70)
    print("\nДля детального отчёта см. ARCHITECTURE_AUDIT_REPORT.md")
    print("Для быстрых исправлений см. QUICK_FIX_GUIDE.md\n")

if __name__ == '__main__':
    main()
