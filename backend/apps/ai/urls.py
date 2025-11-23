"""
URL configuration for AI app.
"""

from django.urls import path
from . import views

app_name = "ai"

urlpatterns = [
    # AI recognition
    path('recognize/', views.AIRecognitionView.as_view(), name='recognize-food'),
]
