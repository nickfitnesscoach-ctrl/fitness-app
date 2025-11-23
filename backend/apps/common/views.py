"""
Common views for FoodMind AI.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db import connection
from django.conf import settings
import sys


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring and load balancers.

    GET /health/

    Returns:
        200 OK if service is healthy
        500 ERROR if service has issues
    """
    health_status = {
        'status': 'ok',
        'version': '1.0.0',
        'python_version': f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',
        'debug': settings.DEBUG,
    }

    # Check database connection
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        health_status['database'] = 'ok'
    except Exception as e:
        health_status['status'] = 'error'
        health_status['database'] = f'error: {str(e)}'
        return Response(health_status, status=500)

    return Response(health_status, status=200)


@api_view(['GET'])
@permission_classes([AllowAny])
def readiness_check(request):
    """
    Readiness check endpoint for Kubernetes/Docker.

    GET /ready/

    Checks if the service is ready to accept traffic.
    """
    checks = {
        'status': 'ready',
        'checks': {}
    }

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        checks['checks']['database'] = 'ready'
    except Exception as e:
        checks['status'] = 'not_ready'
        checks['checks']['database'] = f'not_ready: {str(e)}'
        return Response(checks, status=503)

    return Response(checks, status=200)


@api_view(['GET'])
@permission_classes([AllowAny])
def liveness_check(request):
    """
    Liveness check endpoint for Kubernetes/Docker.

    GET /live/

    Simple check that the service is running.
    """
    return Response({'status': 'alive'}, status=200)
