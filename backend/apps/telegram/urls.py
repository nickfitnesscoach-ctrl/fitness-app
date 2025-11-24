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
]
