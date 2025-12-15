"""
Views for Telegram integration.

⚠️ DEPRECATED: DO NOT USE THIS FILE DIRECTLY ⚠️

This file is kept for backward compatibility ONLY.
All code has been moved to domain-specific modules:
  - Authentication: apps.telegram.auth.views
  - Bot API: apps.telegram.bot.views
  - Trainer Panel: apps.telegram.trainer_panel.views

Please update your imports to use the new structure.
This file may be removed in a future version.
"""

# Re-export from new modules for backward compatibility
from apps.telegram.auth.views import (
    trainer_admin_panel,
    trainer_panel_auth,
    telegram_auth,
    webapp_auth,
    telegram_profile,
)

from apps.telegram.bot.views import (
    save_test_results,
    get_user_or_create,
    create_survey,
    create_plan,
    count_plans_today,
    get_invite_link,
)

from apps.telegram.trainer_panel.views import (
    get_applications_api,
    clients_list,
    client_detail,
)

__all__ = [
    'trainer_admin_panel',
    'trainer_panel_auth',
    'telegram_auth',
    'webapp_auth',
    'telegram_profile',
    'save_test_results',
    'get_applications_api',
    'clients_list',
    'client_detail',
    'get_invite_link',
    'get_user_or_create',
    'create_survey',
    'create_plan',
    'count_plans_today',
]
