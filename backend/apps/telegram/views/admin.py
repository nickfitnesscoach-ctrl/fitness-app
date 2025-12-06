"""
Admin/Trainer panel views for Telegram integration.
"""

import logging

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.telegram.telegram_auth import TelegramAdminPermission
from apps.telegram.models import TelegramUser

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Telegram'],
    summary="Get all clients/applications",
    description="Получить список всех клиентов, прошедших опрос через бота"
)
@api_view(['GET'])
@permission_classes([TelegramAdminPermission])
def get_applications_api(request):
    """
    API endpoint для получения списка клиентов.

    GET /api/v1/telegram/applications/
    """
    clients = TelegramUser.objects.filter(ai_test_completed=True).only(
        'id', 'telegram_id', 'first_name', 'last_name', 'username',
        'ai_test_completed', 'recommended_calories', 'recommended_protein',
        'recommended_fat', 'recommended_carbs', 'created_at'
    ).order_by('-created_at')

    data = []
    for client in clients:
        data.append({
            "id": client.id,
            "telegram_id": str(client.telegram_id),
            "first_name": client.first_name or "",
            "last_name": client.last_name or "",
            "username": client.username or "",
            "display_name": client.display_name,
            "ai_test_completed": client.ai_test_completed,
            "recommended_calories": client.recommended_calories,
            "recommended_protein": client.recommended_protein,
            "recommended_fat": client.recommended_fat,
            "recommended_carbs": client.recommended_carbs,
            "created_at": client.created_at.isoformat(),
        })

    return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Telegram'],
    summary="Get list of clients",
    description="Получить список всех клиентов (applications с флагом is_client=True)"
)
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def clients_list(request):
    """
    GET: Получить список клиентов
    POST: Добавить заявку в клиенты
    
    GET /api/v1/telegram/clients/
    POST /api/v1/telegram/clients/
    """
    if request.method == 'GET':
        clients = TelegramUser.objects.filter(
            ai_test_completed=True,
            is_client=True
        ).only(
            'id', 'telegram_id', 'first_name', 'last_name', 'username',
            'ai_test_completed', 'recommended_calories', 'recommended_protein',
            'recommended_fat', 'recommended_carbs', 'created_at'
        ).order_by('-created_at')
        
        data = []
        for client in clients:
            data.append({
                "id": client.id,
                "telegram_id": str(client.telegram_id),
                "first_name": client.first_name or "",
                "last_name": client.last_name or "",
                "username": client.username or "",
                "display_name": client.display_name,
                "ai_test_completed": client.ai_test_completed,
                "recommended_calories": client.recommended_calories,
                "recommended_protein": client.recommended_protein,
                "recommended_fat": client.recommended_fat,
                "recommended_carbs": client.recommended_carbs,
                "created_at": client.created_at.isoformat(),
            })
        
        return Response(data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        client_id = request.data.get('id')
        
        if not client_id:
            return Response(
                {"error": "ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            telegram_user = TelegramUser.objects.get(id=client_id)
            telegram_user.is_client = True
            telegram_user.save()
            
            return Response({
                "status": "success",
                "message": "Client added successfully",
                "id": telegram_user.id
            }, status=status.HTTP_200_OK)
            
        except TelegramUser.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )


@extend_schema(
    tags=['Telegram'],
    summary="Delete client",
    description="Удалить клиента (убрать флаг is_client)"
)
@api_view(['DELETE'])
@permission_classes([AllowAny])
def client_detail(request, client_id):
    """
    DELETE: Удалить клиента
    
    DELETE /api/v1/telegram/clients/{id}/
    """
    try:
        telegram_user = TelegramUser.objects.get(id=client_id)
        telegram_user.is_client = False
        telegram_user.save()
        
        return Response({
            "status": "success",
            "message": "Client removed successfully"
        }, status=status.HTTP_200_OK)
        
    except TelegramUser.DoesNotExist:
        return Response(
            {"error": "Client not found"},
            status=status.HTTP_404_NOT_FOUND
        )
