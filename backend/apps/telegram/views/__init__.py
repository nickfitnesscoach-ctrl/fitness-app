"""
Telegram views module.
"""

from .auth import (
    trainer_admin_panel,
    trainer_panel_auth,
    telegram_auth,
    webapp_auth,
    telegram_profile,
)
from .test_results import save_test_results
from .admin import (
    get_applications_api,
    clients_list,
    client_detail,
)
from .bot import (
    get_invite_link,
    get_user_or_create,
    create_survey,
    create_plan,
    count_plans_today,
)

__all__ = [
    # Auth
    'trainer_admin_panel',
    'trainer_panel_auth',
    'telegram_auth',
    'webapp_auth',
    'telegram_profile',
    # Test results
    'save_test_results',
    # Admin
    'get_applications_api',
    'clients_list',
    'client_detail',
    # Bot
    'get_invite_link',
    'get_user_or_create',
    'create_survey',
    'create_plan',
    'count_plans_today',
]
