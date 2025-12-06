"""
URL configuration for AI app.
"""

from django.urls import path
from . import views

app_name = "ai"

urlpatterns = [
    # AI recognition (sync or async based on AI_ASYNC_ENABLED setting)
    path('recognize/', views.AIRecognitionView.as_view(), name='recognize-food'),
    
    # Task status endpoint (for async mode polling)
    path('task/<str:task_id>/', views.TaskStatusView.as_view(), name='task-status'),
]
