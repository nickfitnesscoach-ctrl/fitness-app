"""
URL configuration for Telegram app.
"""

from django.urls import path

from .views import (
    telegram_auth,
    webapp_auth,
    trainer_admin_panel,
    telegram_profile,
    save_test_results,
    get_applications_api,
    clients_list,
    client_detail,
    get_invite_link,
    get_user_or_create,
    create_survey,
    create_plan,
    count_plans_today,
)

urlpatterns = [
    # Аутентификация через Telegram Mini App
    path('auth/', telegram_auth, name='telegram-auth'),

    # Единый endpoint для WebApp авторизации (Этап 2 roadmap)
    path('webapp/auth/', webapp_auth, name='webapp-auth'),

    # Trainer admin panel (Telegram WebApp only)
    path('trainer/admin-panel/', trainer_admin_panel, name='trainer-admin-panel'),

    # Профиль Telegram пользователя
    path('profile/', telegram_profile, name='telegram-profile'),

    # Сохранение результатов AI теста от бота
    path('save-test/', save_test_results, name='save-test-results'),

    # Получение списка клиентов/заявок
    path('applications/', get_applications_api, name='telegram-applications'),

    # Управление клиентами
    path('clients/', clients_list, name='telegram-clients-list'),
    path('clients/<int:client_id>/', client_detail, name='telegram-client-detail'),

    # Получить ссылку-приглашение
    path('invite-link/', get_invite_link, name='telegram-invite-link'),

    # Personal Plan API (для бота)
    path('users/get-or-create/', get_user_or_create, name='telegram-user-get-or-create'),
    path('personal-plan/survey/', create_survey, name='personal-plan-create-survey'),
    path('personal-plan/plan/', create_plan, name='personal-plan-create-plan'),
    path('personal-plan/count-today/', count_plans_today, name='personal-plan-count-today'),
]
