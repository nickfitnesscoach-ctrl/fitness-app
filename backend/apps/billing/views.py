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
import logging

from apps.common.audit import SecurityAuditLogger

from .models import SubscriptionPlan, Subscription, Payment, Refund
from .serializers import (
    SubscriptionPlanSerializer,
    SubscriptionSerializer,
    PaymentSerializer,
    SubscribeSerializer,
    CurrentPlanResponseSerializer,
)
from .services import YooKassaService

logger = logging.getLogger(__name__)


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
            if current_subscription.plan.name in ['MONTHLY', 'YEARLY'] and current_subscription.is_active:
                # Разрешаем докупить время к текущему плану
                if current_subscription.plan.name != plan_name:
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
        if subscription.plan.name == 'FREE':
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
    payments = Payment.objects.filter(user=request.user).order_by('-created_at')

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
