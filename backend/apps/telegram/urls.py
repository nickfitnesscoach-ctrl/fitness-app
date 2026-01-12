"""
URL configuration for Telegram app.
"""

from django.urls import path

from apps.telegram.auth.views import (
    telegram_auth,
    telegram_profile,
    trainer_panel_auth,
    webapp_auth,
)
from apps.telegram.bot.views import (
    count_plans_today,
    create_plan,
    create_survey,
    get_invite_link,
    get_user_or_create,
    save_test_results,
)
from apps.telegram.trainer_panel_views import (
    client_detail,
    clients_list,
    get_applications_api,
    get_subscribers_api,
)

urlpatterns = [
    # Аутентификация через Telegram Mini App
    path("auth/", telegram_auth, name="telegram-auth"),
    # Единый endpoint для WebApp авторизации (Этап 2 roadmap)
    path("webapp/auth/", webapp_auth, name="webapp-auth"),
    # Trainer admin panel (Telegram WebApp only)
    path("trainer/admin-panel/", trainer_panel_auth, name="trainer-admin-panel"),
    # Профиль Telegram пользователя
    path("profile/", telegram_profile, name="telegram-profile"),
    # Сохранение результатов AI теста от бота
    path("save-test/", save_test_results, name="save-test-results"),
    # Получение списка клиентов/заявок
    path("applications/", get_applications_api, name="telegram-applications"),
    # Управление клиентами
    path("clients/", clients_list, name="telegram-clients-list"),
    path("clients/<int:client_id>/", client_detail, name="telegram-client-detail"),
    # Получить ссылку-приглашение
    path("invite-link/", get_invite_link, name="telegram-get-invite-link"),
    # Статистика подписчиков и выручки
    path("subscribers/", get_subscribers_api, name="telegram-subscribers"),
    # Personal Plan API (для бота)
    path("users/get-or-create/", get_user_or_create, name="telegram-user-get-or-create"),
    path("personal-plan/survey/", create_survey, name="personal-plan-create-survey"),
    path("personal-plan/plan/", create_plan, name="personal-plan-create-plan"),
    path("personal-plan/count-today/", count_plans_today, name="personal-plan-count-today"),
]
