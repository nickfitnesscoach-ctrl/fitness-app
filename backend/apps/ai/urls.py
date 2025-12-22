"""
urls.py — маршруты AI модуля.

Простыми словами:
- здесь перечислены URL-адреса, по которым фронт обращается к AI.
"""

from __future__ import annotations

from django.urls import path

from .views import AIRecognitionView, TaskStatusView

app_name = "ai"

urlpatterns = [
    # Отправить фото → получить task_id (async) или результат (sync в dev)
    path("recognize/", AIRecognitionView.as_view(), name="recognize-food"),
    # Проверять статус задачи по task_id (polling)
    path("task/<str:task_id>/", TaskStatusView.as_view(), name="task-status"),
]
