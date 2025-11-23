"""
URL configuration for nutrition app (REST API docs specification).

Public endpoints:
- GET /api/v1/meals/?date=YYYY-MM-DD - daily diary with stats
- POST /api/v1/meals/ - create meal
- GET/PUT/PATCH/DELETE /api/v1/meals/{id}/ - meal CRUD
- POST /api/v1/meals/{meal_id}/items/ - add food item (nested)
- GET/PUT/PATCH/DELETE /api/v1/meals/{meal_id}/items/{id}/ - food item CRUD (nested)

Goals endpoints (internal):
- GET /api/v1/nutrition/goals/ - get current goal
- POST /api/v1/nutrition/goals/calculate/ - calculate goal
- POST /api/v1/nutrition/goals/set-auto/ - set auto goal
- PUT/PATCH /api/v1/nutrition/goals/ - update goal manually
"""

from django.urls import path
from . import views

app_name = "nutrition"

urlpatterns = [
    # Meals (public API per REST docs)
    path('meals/', views.MealListCreateView.as_view(), name='meal-list'),
    path('meals/<int:pk>/', views.MealDetailView.as_view(), name='meal-detail'),

    # Food items (nested under meals per REST docs)
    path('meals/<int:meal_id>/items/', views.FoodItemCreateView.as_view(), name='food-item-create'),
    path('meals/<int:meal_id>/items/<int:pk>/', views.FoodItemDetailView.as_view(), name='food-item-detail'),

    # Daily goals (internal endpoints, documented in REST docs Section 4)
    path('goals/', views.DailyGoalView.as_view(), name='daily-goal'),
    path('goals/calculate/', views.CalculateGoalsView.as_view(), name='calculate-goals'),
    path('goals/set-auto/', views.SetAutoGoalView.as_view(), name='set-auto-goal'),
]
