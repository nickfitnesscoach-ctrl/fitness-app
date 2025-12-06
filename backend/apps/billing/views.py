"""
Views для управления тарифами, подписками и платежами.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from decimal import Decimal
import logging

from apps.common.audit import SecurityAuditLogger

from .models import SubscriptionPlan, Subscription, Payment, Refund
from .serializers import (
    SubscriptionPlanSerializer,
    SubscriptionSerializer,
    PaymentSerializer,
    SubscribeSerializer,
    CurrentPlanResponseSerializer,
    SubscriptionStatusSerializer,
    PaymentMethodSerializer,
    AutoRenewToggleSerializer,
    PaymentHistoryItemSerializer,
    SubscriptionPlanPublicSerializer,
)
from .services import YooKassaService

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_subscription_plans(request):
    """
    GET /api/v1/billing/plans/
    Получение списка всех активных тарифных планов (публичный endpoint).

    Response (200):
        [
            {
                "code": "FREE",
                "display_name": "Бесплатный",
                "price": 0,
                "duration_days": 0,
                "daily_photo_limit": 3,
                "history_days": 7,
                "ai_recognition": true,
                "advanced_stats": false,
                "priority_support": false
            },
            {
                "code": "PRO_MONTHLY",
                "display_name": "PRO месяц",
                "price": 299,
                "duration_days": 30,
                "daily_photo_limit": null,
                "history_days": -1,
                "ai_recognition": true,
                "advanced_stats": true,
                "priority_support": true
            },
            {
                "code": "PRO_YEARLY",
                "display_name": "PRO год",
                "price": 2490,
                "duration_days": 365,
                "daily_photo_limit": null,
                "history_days": -1,
                "ai_recognition": true,
                "advanced_stats": true,
                "priority_support": true
            }
        ]

    Доступ: AllowAny (публично, без авторизации)
    """
    # Получаем все активные планы (исключая тестовые)
    plans = SubscriptionPlan.objects.filter(
        is_active=True,
        is_test=False
    ).order_by('price')

    serializer = SubscriptionPlanPublicSerializer(plans, many=True)

    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_plan(request):
    """
    GET /api/v1/billing/plan
    Получение информации о текущем тарифном плане пользователя.
    """
    try:
        # Получаем подписку пользователя
        subscription = request.user.subscription
    except Subscription.DoesNotExist:
        return Response(
            {
                'error': {
                    'code': 'NO_SUBSCRIPTION',
                    'message': 'У вас нет активной подписки'
                }
            },
            status=status.HTTP_404_NOT_FOUND
        )

    # Получаем все доступные активные планы (кроме FREE)
    available_plans = SubscriptionPlan.objects.filter(
        is_active=True
    ).exclude(name='FREE')

    response_data = {
        'subscription': SubscriptionSerializer(subscription).data,
        'available_plans': SubscriptionPlanSerializer(available_plans, many=True).data
    }

    return Response({
        'status': 'success',
        'data': response_data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscribe(request):
    """
    POST /api/v1/billing/subscribe
    Оформление новой подписки.
    """
    serializer = SubscribeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    plan_name = serializer.validated_data['plan']

    try:
        # Получаем план
        plan = SubscriptionPlan.objects.get(name=plan_name, is_active=True)

        # Создаём платёж с блокировкой подписки для предотвращения race condition
        with transaction.atomic():
            # Блокируем подписку пользователя для предотвращения параллельных платежей
            current_subscription = Subscription.objects.select_for_update().get(user=request.user)

            # Проверяем, что у пользователя нет активного платного плана
            if current_subscription.plan.code in ['MONTHLY', 'YEARLY', 'PRO_MONTHLY', 'PRO_YEARLY'] and current_subscription.is_active:
                # Разрешаем докупить время к текущему плану
                if current_subscription.plan.code != plan_name:
                    return Response(
                        {
                            'error': {
                                'code': 'ACTIVE_SUBSCRIPTION',
                                'message': f'У вас уже есть активная подписка "{current_subscription.plan.display_name}". Дождитесь её окончания или отмените автопродление.'
                            }
                        },
                        status=status.HTTP_409_CONFLICT
                    )
            # Создаём запись платежа
            payment = Payment.objects.create(
                user=request.user,
                subscription=current_subscription,
                plan=plan,
                amount=plan.price,
                currency='RUB',
                status='PENDING',
                provider='YOOKASSA',
                description=f'Подписка {plan.display_name}',
                save_payment_method=True,  # Сохраняем способ оплаты для автопродления
            )

            # Создаём платёж в YooKassa
            return_url = request.build_absolute_uri('/') + 'payment-success'

            # Initialize YooKassa service (validates credentials)
            yookassa_service = YooKassaService()

            yookassa_payment = yookassa_service.create_payment(
                amount=plan.price,
                description=f'Подписка {plan.display_name}',
                return_url=return_url,
                save_payment_method=True,
                metadata={
                    'payment_id': str(payment.id),
                    'user_id': str(request.user.id),
                    'plan_name': plan_name,
                }
            )

            # Обновляем payment_id от YooKassa
            payment.yookassa_payment_id = yookassa_payment['id']
            payment.save()

            # SECURITY: Log payment creation
            SecurityAuditLogger.log_payment_created(
                user=request.user,
                amount=float(plan.price),
                plan=plan_name,
                request=request
            )

        return Response({
            'status': 'success',
            'message': 'Платёж создан. Перейдите по ссылке для оплаты.',
            'data': {
                'payment_id': str(payment.id),
                'amount': str(plan.price),
                'confirmation_url': yookassa_payment['confirmation_url'],
            }
        }, status=status.HTTP_201_CREATED)

    except SubscriptionPlan.DoesNotExist:
        return Response(
            {
                'error': {
                    'code': 'INVALID_PLAN',
                    'message': f'Тарифный план "{plan_name}" не найден'
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Subscribe error: {str(e)}")
        return Response(
            {
                'error': {
                    'code': 'PAYMENT_ERROR',
                    'message': 'Не удалось создать платёж. Попробуйте позже.'
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_auto_renew(request):
    """
    POST /api/v1/billing/auto-renew/toggle
    Включение/отключение автопродления подписки.
    """
    try:
        subscription = request.user.subscription

        # Проверяем, что это не бесплатный план
        if subscription.plan.code == 'FREE':
            return Response(
                {
                    'error': {
                        'code': 'NOT_AVAILABLE_FOR_FREE',
                        'message': 'Автопродление недоступно для бесплатного плана'
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверяем, что есть сохранённый способ оплаты
        if not subscription.yookassa_payment_method_id:
            return Response(
                {
                    'error': {
                        'code': 'NO_PAYMENT_METHOD',
                        'message': 'Для автопродления необходим сохранённый способ оплаты. Оформите новую подписку.'
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Включаем автопродление - проверка валидности payment_method будет при следующем платеже
        # Если payment_method станет невалидным, рекуррентный платеж не пройдет
        # и webhook обработчик должен уведомить пользователя
        subscription.auto_renew = not subscription.auto_renew
        subscription.save()

        message = 'Автопродление включено' if subscription.auto_renew else 'Автопродление отключено'

        return Response({
            'status': 'success',
            'message': message,
            'data': {
                'auto_renew': subscription.auto_renew
            }
        })

    except Subscription.DoesNotExist:
        return Response(
            {
                'error': {
                    'code': 'NO_SUBSCRIPTION',
                    'message': 'У вас нет активной подписки'
                }
            },
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_history(request):
    """
    GET /api/v1/billing/payments
    Получение истории платежей пользователя.
    """
    payments = Payment.objects.filter(user=request.user).select_related('plan').order_by('-created_at')

    # Пагинация
    paginator = PageNumberPagination()
    paginator.page_size = request.query_params.get('page_size', 20)
    paginated_payments = paginator.paginate_queryset(payments, request)

    serializer = PaymentSerializer(paginated_payments, many=True)

    return Response({
        'status': 'success',
        'data': {
            'count': payments.count(),
            'next': paginator.get_next_link(),
            'previous': paginator.get_previous_link(),
            'results': serializer.data
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payment(request):
    """
    POST /api/v1/billing/create-payment/
    Универсальное создание платежа для любого тарифного плана.

    ВАЖНО: Сумма платежа берется с бэкенда из SubscriptionPlan.price,
    а НЕ из фронтенда. Фронтенд отправляет только plan_code.

    Body:
        {
            "plan_code": "PRO_MONTHLY" | "PRO_YEARLY",  // Системный код тарифа
            "return_url": "https://example.com/success"  // опционально
        }

    Response (201):
        {
            "payment_id": "uuid",
            "yookassa_payment_id": "...",
            "confirmation_url": "https://..."
        }

    Errors:
        - 400: План не найден, невалиден или FREE
        - 502: Ошибка создания платежа в YooKassa

    Примеры plan_code:
        - "PRO_MONTHLY": Месячная подписка PRO (цена берется из БД)
        - "PRO_YEARLY": Годовая подписка PRO (цена берется из БД)
        - "MONTHLY", "YEARLY": Legacy коды (поддерживаются для обратной совместимости)
    """
    from .services import create_subscription_payment

    # Валидация входных данных
    plan_code = request.data.get('plan_code')
    if not plan_code:
        return Response(
            {
                'error': {
                    'code': 'MISSING_PLAN_CODE',
                    'message': 'Укажите plan_code в теле запроса'
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Получаем кастомный return_url из body или используем дефолтный
    return_url = request.data.get('return_url')

    try:
        # Создаем платеж
        payment, confirmation_url = create_subscription_payment(
            user=request.user,
            plan_code=plan_code,
            return_url=return_url
        )

        # SECURITY: Log payment creation
        SecurityAuditLogger.log_payment_created(
            user=request.user,
            amount=float(payment.amount),
            plan=plan_code,
            request=request
        )

        return Response(
            {
                'payment_id': str(payment.id),
                'yookassa_payment_id': payment.yookassa_payment_id,
                'confirmation_url': confirmation_url,
            },
            status=status.HTTP_201_CREATED
        )

    except ValueError as e:
        return Response(
            {
                'error': {
                    'code': 'INVALID_PLAN',
                    'message': str(e)
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Create payment error: {str(e)}", exc_info=True)
        return Response(
            {
                'error': {
                    'code': 'PAYMENT_CREATE_FAILED',
                    'message': 'Не удалось создать платеж. Попробуйте позже.'
                }
            },
            status=status.HTTP_502_BAD_GATEWAY
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bind_card_start(request):
    """
    POST /api/v1/billing/bind-card/start/
    Запуск процесса привязки карты без оплаты подписки.

    Создаёт платёж на 1₽ для сохранения карты для автопродления.
    Пользователь берётся из контекста авторизации.

    Body (опционально):
        {
            "return_url": "https://example.com/success"  // Кастомный URL возврата
        }

    Response (201):
        {
            "confirmation_url": "https://...",
            "payment_id": "uuid"
        }

    Errors:
        - 502: Ошибка создания платежа в YooKassa
    """
    from .models import Payment
    from django.conf import settings

    # Получаем return_url из body или используем дефолтный
    return_url = request.data.get('return_url') or settings.YOOKASSA_RETURN_URL

    try:
        # Инициализируем YooKassa сервис
        yookassa_service = YooKassaService()

        # Создаём платёж на 1₽ для привязки карты
        payment_result = yookassa_service.create_payment(
            amount=Decimal('1.00'),
            description='Привязка карты для автопродления PRO',
            return_url=return_url,
            save_payment_method=True,
            metadata={
                'user_id': str(request.user.id),
                'purpose': 'card_binding',
            }
        )

        # Сохраняем платёж в БД
        payment = Payment.objects.create(
            user=request.user,
            subscription=request.user.subscription,
            amount=Decimal('1.00'),
            currency='RUB',
            status='PENDING',
            yookassa_payment_id=payment_result['id'],
            description='Привязка карты для автопродления PRO',
            save_payment_method=True,
            is_recurring=False,
        )

        # SECURITY: Log card binding attempt
        SecurityAuditLogger.log_payment_created(
            user=request.user,
            amount=1.0,
            plan='card_binding',
            request=request
        )

        logger.info(
            f"Card binding payment created for user {request.user.id}: "
            f"payment_id={payment.id}, yookassa_id={payment_result['id']}"
        )

        return Response(
            {
                'confirmation_url': payment_result['confirmation_url'],
                'payment_id': str(payment.id),
            },
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        logger.error(f"Card binding payment creation error: {str(e)}", exc_info=True)
        return Response(
            {
                'detail': 'cannot_create_binding_payment',
                'error': {
                    'code': 'BINDING_PAYMENT_CREATE_FAILED',
                    'message': 'Не удалось создать платёж для привязки карты. Попробуйте позже.'
                }
            },
            status=status.HTTP_502_BAD_GATEWAY
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_test_live_payment(request):
    """
    POST /api/v1/billing/create-test-live-payment/
    Создание ТЕСТОВОГО платежа за 1₽ на боевом магазине YooKassa.

    ДОСТУП: Только для владельца/админов (проверка по TELEGRAM_ADMINS).

    Используется для проверки:
    - Корректности настройки live credentials
    - Работы webhooks на боевом магазине
    - Полного цикла: оплата → webhook → обновление БД → отображение в UI

    Body (опционально):
        {
            "return_url": "https://example.com/success"  // Кастомный URL возврата
        }

    Response (201):
        {
            "payment_id": "uuid",
            "yookassa_payment_id": "...",
            "confirmation_url": "https://...",
            "test_mode": true,
            "amount": "1.00"
        }

    Errors:
        - 403: Доступ запрещён (пользователь не является админом)
        - 404: Тестовый план не найден (запустите миграции)
        - 502: Ошибка создания платежа в YooKassa
    """
    from .services import create_subscription_payment
    from .models import SubscriptionPlan
    from django.conf import settings

    # SECURITY: Проверка прав доступа (только админы)
    telegram_user = getattr(request.user, 'telegram_profile', None)
    if not telegram_user:
        return Response(
            {
                'error': {
                    'code': 'FORBIDDEN',
                    'message': 'Доступ запрещён: пользователь не привязан к Telegram'
                }
            },
            status=status.HTTP_403_FORBIDDEN
        )

    telegram_admins = getattr(settings, 'TELEGRAM_ADMINS', set())
    is_admin = telegram_user.telegram_id in telegram_admins

    if not is_admin:
        logger.warning(
            f"Unauthorized test payment attempt by user {request.user.id} "
            f"(telegram_id: {telegram_user.telegram_id})"
        )
        return Response(
            {
                'error': {
                    'code': 'FORBIDDEN',
                    'message': 'Доступ запрещён: только для админов'
                }
            },
            status=status.HTTP_403_FORBIDDEN
        )

    # Получаем тестовый план
    try:
        test_plan = SubscriptionPlan.objects.get(name='TEST_LIVE', is_test=True)
    except SubscriptionPlan.DoesNotExist:
        logger.error("Test plan TEST_LIVE not found. Run migrations first.")
        return Response(
            {
                'error': {
                    'code': 'TEST_PLAN_NOT_FOUND',
                    'message': 'Тестовый план не найден. Запустите миграции: python manage.py migrate billing'
                }
            },
            status=status.HTTP_404_NOT_FOUND
        )

    # Получаем кастомный return_url из body или используем дефолтный
    return_url = request.data.get('return_url')

    try:
        # Создаем платеж через тестовый план
        # ВАЖНО: save_payment_method=False, т.к. боевой магазин может не поддерживать рекуррентные платежи
        payment, confirmation_url = create_subscription_payment(
            user=request.user,
            plan_code='TEST_LIVE',
            return_url=return_url,
            save_payment_method=False  # Не сохраняем карту для тестового платежа
        )

        # SECURITY: Log test payment creation
        SecurityAuditLogger.log_payment_created(
            user=request.user,
            amount=float(payment.amount),
            plan='TEST_LIVE (admin test)',
            request=request
        )

        logger.info(
            f"Test live payment created by admin {request.user.id} "
            f"(telegram_id: {telegram_user.telegram_id}). "
            f"Payment ID: {payment.id}, YooKassa Mode: {settings.YOOKASSA_MODE}"
        )

        return Response(
            {
                'payment_id': str(payment.id),
                'yookassa_payment_id': payment.yookassa_payment_id,
                'confirmation_url': confirmation_url,
                'test_mode': True,
                'amount': str(payment.amount),
                'yookassa_mode': settings.YOOKASSA_MODE,
            },
            status=status.HTTP_201_CREATED
        )

    except ValueError as e:
        return Response(
            {
                'error': {
                    'code': 'INVALID_PLAN',
                    'message': str(e)
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Test payment creation error: {str(e)}", exc_info=True)
        return Response(
            {
                'error': {
                    'code': 'PAYMENT_CREATE_FAILED',
                    'message': f'Не удалось создать тестовый платёж: {str(e)}'
                }
            },
            status=status.HTTP_502_BAD_GATEWAY
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_plus_payment(request):
    """
    POST /api/v1/billing/create-plus-payment/
    Создание платежа для подписки Pro (месячный план MONTHLY).

    Body (опционально):
        {
            "return_url": "https://example.com/success"  // Кастомный URL возврата
        }

    Response:
        {
            "payment_id": "uuid",
            "yookassa_payment_id": "...",
            "confirmation_url": "https://..."
        }
    """
    from .services import create_monthly_subscription_payment

    # Получаем кастомный return_url из body или используем дефолтный
    return_url = request.data.get('return_url')

    try:
        # Создаем платеж
        payment, confirmation_url = create_monthly_subscription_payment(
            user=request.user,
            return_url=return_url
        )

        # SECURITY: Log payment creation
        SecurityAuditLogger.log_payment_created(
            user=request.user,
            amount=float(payment.amount),
            plan='MONTHLY',
            request=request
        )

        return Response(
            {
                'payment_id': str(payment.id),
                'yookassa_payment_id': payment.yookassa_payment_id,
                'confirmation_url': confirmation_url,
            },
            status=status.HTTP_201_CREATED
        )

    except ValueError as e:
        return Response(
            {
                'error': {
                    'code': 'PAYMENT_CREATE_FAILED',
                    'message': str(e)
                }
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Create plus payment error: {str(e)}", exc_info=True)
        return Response(
            {
                'error': {
                    'code': 'PAYMENT_CREATE_FAILED',
                    'message': 'Не удалось создать платеж. Попробуйте позже.'
                }
            },
            status=status.HTTP_502_BAD_GATEWAY
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_subscription_status(request):
    """
    GET /api/v1/billing/me/
    Получение текущего статуса подписки пользователя с лимитами и использованием.

    Response:
        {
            "plan_code": "FREE" | "MONTHLY" | "YEARLY",
            "plan_name": "Бесплатный" | "Pro Месячный" | "Pro Годовой",
            "expires_at": "2024-12-31T23:59:59Z" или null для FREE,
            "is_active": true/false,
            "daily_photo_limit": 3 или null (безлимит),
            "used_today": 2,
            "remaining_today": 1 или null (безлимит),
            "test_live_payment_available": true/false  // Только для админов в prod режиме
        }
    """
    from .services import get_effective_plan_for_user
    from .usage import DailyUsage

    # Получаем действующий план пользователя
    plan = get_effective_plan_for_user(request.user)

    # Получаем использование на сегодня
    usage = DailyUsage.objects.get_today(request.user)
    used_today = usage.photo_ai_requests

    # Вычисляем остаток
    if plan.daily_photo_limit is not None:
        remaining_today = max(0, plan.daily_photo_limit - used_today)
    else:
        remaining_today = None

    # Получаем информацию о подписке (если есть)
    try:
        subscription = request.user.subscription
        is_active = subscription.is_active and not subscription.is_expired()
        expires_at = subscription.end_date.isoformat() if subscription.plan.code != 'FREE' else None
    except Subscription.DoesNotExist:
        is_active = True  # FREE план всегда активен
        expires_at = None

    # Проверяем, доступна ли кнопка тестового платежа (только для админов в prod режиме)
    from django.conf import settings
    test_live_payment_available = False

    telegram_user = getattr(request.user, 'telegram_profile', None)
    if telegram_user:
        telegram_admins = getattr(settings, 'TELEGRAM_ADMINS', set())
        is_admin = telegram_user.telegram_id in telegram_admins
        is_prod_mode = settings.YOOKASSA_MODE == 'prod'
        test_live_payment_available = is_admin and is_prod_mode

        # DEBUG logging
        logger.info(
            f"[TEST_PAYMENT_BUTTON] user_id={request.user.id}, "
            f"telegram_id={telegram_user.telegram_id}, "
            f"telegram_admins={telegram_admins}, "
            f"is_admin={is_admin}, "
            f"yookassa_mode={settings.YOOKASSA_MODE}, "
            f"is_prod_mode={is_prod_mode}, "
            f"test_live_payment_available={test_live_payment_available}"
        )

    response_data = {
        'plan_code': plan.code,
        'plan_name': plan.display_name,
        'expires_at': expires_at,
        'is_active': is_active,
        'daily_photo_limit': plan.daily_photo_limit,
        'used_today': used_today,
        'remaining_today': remaining_today,
        'test_live_payment_available': test_live_payment_available,
    }

    return Response(response_data)


# ============================================================
# NEW ENDPOINTS: Settings screen API
# ============================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_subscription_details(request):
    """
    GET /api/v1/billing/subscription/
    Получение полной информации о подписке для экрана "Настройки".

    Response:
        {
            "plan": "free" | "pro",
            "plan_display": "Free" | "PRO",
            "expires_at": "2025-12-26" или null,
            "is_active": true/false,
            "autorenew_available": true/false,
            "autorenew_enabled": true/false,
            "card_bound": true/false,
            "payment_method": {
                "is_attached": true/false,
                "card_mask": "•••• 1234" или null,
                "card_brand": "Visa" или null
            }
        }
    """
    try:
        subscription = request.user.subscription
    except Subscription.DoesNotExist:
        # Если подписки нет, возвращаем FREE план
        return Response({
            'plan': 'free',
            'plan_display': 'Free',
            'expires_at': None,
            'is_active': True,
            'autorenew_available': False,
            'autorenew_enabled': False,
            'card_bound': False,
            'payment_method': {
                'is_attached': False,
                'card_mask': None,
                'card_brand': None
            }
        })

    # Определяем plan (free или pro)
    plan_code = subscription.plan.code
    if plan_code == 'FREE':
        plan = 'free'
        plan_display = 'Free'
    else:
        plan = 'pro'
        plan_display = 'PRO'

    # Определяем expires_at
    if subscription.plan.code == 'FREE':
        expires_at = None
    else:
        expires_at = subscription.end_date.date() if subscription.end_date else None

    # Проверяем активность
    is_active = subscription.is_active and not subscription.is_expired()

    # Автопродление доступно, если есть payment_method
    autorenew_available = bool(subscription.yookassa_payment_method_id)

    # Автопродление включено
    autorenew_enabled = subscription.auto_renew

    # Информация о способе оплаты
    payment_method = {
        'is_attached': bool(subscription.yookassa_payment_method_id),
        'card_mask': subscription.card_mask,
        'card_brand': subscription.card_brand
    }

    response_data = {
        'plan': plan,
        'plan_display': plan_display,
        'expires_at': expires_at,
        'is_active': is_active,
        'autorenew_available': autorenew_available,
        'autorenew_enabled': autorenew_enabled,
        'card_bound': bool(subscription.yookassa_payment_method_id),  # Explicit card_bound flag
        'payment_method': payment_method
    }

    return Response(response_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_auto_renew(request):
    """
    POST /api/v1/billing/subscription/autorenew/
    Включение/отключение автопродления.

    Request Body:
        {
            "enabled": true | false
        }

    Response:
        Возвращает тот же формат, что и GET /billing/subscription/
    """
    serializer = AutoRenewToggleSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    enabled = serializer.validated_data['enabled']

    try:
        subscription = request.user.subscription

        # Проверяем, что это не бесплатный план
        if subscription.plan.code == 'FREE':
            return Response(
                {
                    'error': {
                        'code': 'NOT_AVAILABLE_FOR_FREE',
                        'message': 'Автопродление недоступно для бесплатного плана'
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Если пытаемся включить, проверяем наличие payment_method
        if enabled and not subscription.yookassa_payment_method_id:
            return Response(
                {
                    'error': {
                        'code': 'payment_method_required',
                        'message': 'Для автопродления необходима привязанная карта. Оформите подписку с сохранением карты.'
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Обновляем флаг
        subscription.auto_renew = enabled
        subscription.save()

        # Возвращаем обновленные данные подписки
        return get_subscription_details(request)

    except Subscription.DoesNotExist:
        return Response(
            {
                'error': {
                    'code': 'NO_SUBSCRIPTION',
                    'message': 'У вас нет активной подписки'
                }
            },
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payment_method_details(request):
    """
    GET /api/v1/billing/payment-method/
    Получение информации о привязанном способе оплаты.

    Response:
        {
            "is_attached": true/false,
            "card_mask": "•••• 1234" или null,
            "card_brand": "Visa" или null
        }
    """
    try:
        subscription = request.user.subscription

        response_data = {
            'is_attached': bool(subscription.yookassa_payment_method_id),
            'card_mask': subscription.card_mask,
            'card_brand': subscription.card_brand
        }

        return Response(response_data)

    except Subscription.DoesNotExist:
        # Если подписки нет, возвращаем пустые данные
        return Response({
            'is_attached': False,
            'card_mask': None,
            'card_brand': None
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_payments_history(request):
    """
    GET /api/v1/billing/payments/
    Получение истории платежей пользователя.

    Query parameters:
        - limit: int (default: 10) - количество платежей

    Response:
        {
            "results": [
                {
                    "id": "uuid",
                    "amount": 299,
                    "currency": "RUB",
                    "status": "succeeded",
                    "paid_at": "2025-02-10T12:34:56Z",
                    "description": "PRO месяц"
                },
                ...
            ]
        }
    """
    # Получаем limit из query параметров
    limit = request.query_params.get('limit', 10)
    try:
        limit = int(limit)
        if limit < 1:
            limit = 10
        if limit > 100:
            limit = 100
    except (ValueError, TypeError):
        limit = 10

    # Получаем платежи пользователя
    payments = Payment.objects.filter(
        user=request.user
    ).order_by('-created_at')[:limit]

    # Формируем результат
    results = []
    for payment in payments:
        # Маппинг статусов в lowercase для фронта
        status_map = {
            'PENDING': 'pending',
            'WAITING_FOR_CAPTURE': 'pending',
            'SUCCEEDED': 'succeeded',
            'CANCELED': 'canceled',
            'FAILED': 'failed',
            'REFUNDED': 'refunded',
        }

        results.append({
            'id': str(payment.id),
            'amount': float(payment.amount),
            'currency': payment.currency,
            'status': status_map.get(payment.status, payment.status.lower()),
            'paid_at': payment.paid_at.isoformat() if payment.paid_at else None,
            'description': payment.description
        })

    return Response({
        'results': results
    })
