"""
URL configuration for Telegram app.
"""

from django.urls import path

from . import views

urlpatterns = [
    # Аутентификация через Telegram Mini App
    path('auth/', views.telegram_auth, name='telegram-auth'),

    # Единый endpoint для WebApp авторизации (Этап 2 roadmap)
    path('webapp/auth/', views.webapp_auth, name='webapp-auth'),

    # Trainer admin panel (Telegram WebApp only)
    path('trainer/admin-panel/', views.trainer_admin_panel, name='trainer-admin-panel'),

    # Профиль Telegram пользователя
    path('profile/', views.telegram_profile, name='telegram-profile'),

    # Сохранение результатов AI теста от бота
    path('save-test/', views.save_test_results, name='save-test-results'),

    # Получение списка клиентов/заявок
    path('applications/', views.get_applications_api, name='telegram-applications'),

    # Управление клиентами
    path('clients/', views.clients_list, name='telegram-clients-list'),
    path('clients/<int:client_id>/', views.client_detail, name='telegram-client-detail'),

    # Получить ссылку-приглашение
    path('invite-link/', views.get_invite_link, name='telegram-invite-link'),

    # Personal Plan API (для бота)
    path('users/get-or-create/', views.get_user_or_create, name='telegram-user-get-or-create'),
    path('personal-plan/survey/', views.create_survey, name='personal-plan-create-survey'),
    path('personal-plan/plan/', views.create_plan, name='personal-plan-create-plan'),
    path('personal-plan/count-today/', views.count_plans_today, name='personal-plan-count-today'),
]
