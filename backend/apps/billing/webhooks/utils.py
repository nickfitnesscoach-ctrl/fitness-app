"""
Утилиты для webhook YooKassa.

Задачи этого файла:
1) IP allowlist (разрешаем webhook только с IP YooKassa)
2) безопасное извлечение IP из Django request (если нужно отдельно)
3) маленькие helper'ы без бизнес-логики

Почему это важно:
- webhook — публичная точка входа.
- без IP allowlist любой сможет постучаться и пытаться подделать события.
- allowlist не даёт 100% криптографической защиты, но это сильный базовый слой.
"""

from __future__ import annotations

import ipaddress
from typing import Optional

from django.http import HttpRequest

# ---------------------------------------------------------------------
# YooKassa IP ranges
# ---------------------------------------------------------------------
# Официальные диапазоны IP YooKassa периодически могут меняться.
# Если YooKassa перестала доставлять webhook:
# - проверь актуальность диапазонов на стороне YooKassa
# - обнови список, перезапусти backend
#
# Важно: мы храним как строки, потом парсим в ip_network.
YOOKASSA_IP_RANGES = [
    # IPv4
    "185.71.76.0/27",
    "185.71.77.0/27",
    "77.75.153.0/25",
    "77.75.156.11/32",
    "77.75.156.35/32",
    "77.75.154.128/25",
    "2a02:5180::/32",  # IPv6 (одним блоком; оставлено как есть)
]


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def is_ip_allowed(ip: Optional[str]) -> bool:
    """
    Проверяет, что IP клиента входит в разрешённые диапазоны YooKassa.

    Возвращает:
    - True: если IP валиден и попадает в хотя бы один диапазон
    - False: если IP отсутствует/невалиден/не в allowlist
    """
    if not ip:
        return False

    try:
        client_ip = ipaddress.ip_address(ip)
    except ValueError:
        # Например пришло что-то не похожее на IP
        return False

    for cidr in YOOKASSA_IP_RANGES:
        try:
            if client_ip in ipaddress.ip_network(cidr):
                return True
        except ValueError:
            # Если в списке случайно появится битый CIDR — не падаем
            continue

    return False


def get_client_ip(request: HttpRequest) -> Optional[str]:
    """
    Достаём IP клиента из request.

    Логика:
    - если есть X-Forwarded-For → берём первый IP (самый левый)
    - иначе REMOTE_ADDR

    Примечание:
    - X-Forwarded-For корректен только если ты доверяешь своему reverse proxy
      (nginx / traefik / cloudflare). Иначе заголовок можно подделать.
    - в нашей схеме это вспомогательная функция; основная защита — allowlist.
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
