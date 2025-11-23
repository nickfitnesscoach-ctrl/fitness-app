"""
Views for nutrition app - meals, food items, daily goals.

REST API documentation compliant implementation.
"""

from datetime import date, datetime
from rest_framework import generics, status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from django.shortcuts import get_object_or_404

from .models import Meal, FoodItem, DailyGoal
from .serializers import (
    MealSerializer,
    MealCreateSerializer,
    FoodItemSerializer,
    DailyGoalSerializer,
    DailyStatsSerializer,
    CalculateGoalsSerializer,
)


@extend_schema(tags=['Meals'])
class MealListCreateView(generics.ListCreateAPIView):
    """
    GET /api/v1/meals/?date=YYYY-MM-DD - Get daily diary with nutrition stats
    GET /api/v1/meals/ - List all meals (with pagination)
    POST /api/v1/meals/ - Create new meal
    """

    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MealCreateSerializer
        return MealSerializer

    def get_queryset(self):
        """Filter meals by current user and optionally by date."""
        queryset = Meal.objects.filter(user=self.request.user).prefetch_related('items')

        # Filter by date if provided
        date_str = self.request.query_params.get('date')
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                queryset = queryset.filter(date=target_date)
            except ValueError:
                pass  # Invalid date format, return all meals

        return queryset

    @extend_schema(
        summary="Получить дневник питания за день",
        description="Возвращает все приёмы пищи за указанную дату с общей статистикой КБЖУ и прогрессом выполнения цели. Если date не указан, возвращает все приёмы пищи.",
        parameters=[
            OpenApiParameter(
                name='date',
                type=OpenApiTypes.DATE,
                location=OpenApiParameter.QUERY,
                description='Дата в формате YYYY-MM-DD (опционально)',
                required=False
            )
        ],
        responses={
            200: OpenApiResponse(
                description="Daily diary with meals and nutrition stats",
                response=DailyStatsSerializer
            ),
        }
    )
    def get(self, request, *args, **kwargs):
        """
        Get daily diary with meals and nutrition stats (if ?date= provided).
        Otherwise returns simple list of all meals.
        """
        date_str = request.query_params.get('date')

        if date_str:
            # Return daily stats (as per REST API docs)
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {"error": "Невалидный формат даты. Используйте YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get active daily goal
            try:
                daily_goal = DailyGoal.objects.get(user=request.user, is_active=True)
            except DailyGoal.DoesNotExist:
                return Response(
                    {"error": "Установите дневную цель КБЖУ"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get all meals for the date
            meals = Meal.objects.filter(user=request.user, date=target_date).prefetch_related('items')

            # Calculate total consumed
            total_calories = sum(meal.total_calories for meal in meals)
            total_protein = sum(meal.total_protein for meal in meals)
            total_fat = sum(meal.total_fat for meal in meals)
            total_carbs = sum(meal.total_carbohydrates for meal in meals)

            # Calculate progress percentage
            progress = {
                'calories': round((total_calories / daily_goal.calories * 100), 1) if daily_goal.calories else 0,
                'protein': round((float(total_protein) / float(daily_goal.protein) * 100), 1) if daily_goal.protein else 0,
                'fat': round((float(total_fat) / float(daily_goal.fat) * 100), 1) if daily_goal.fat else 0,
                'carbohydrates': round((float(total_carbs) / float(daily_goal.carbohydrates) * 100), 1) if daily_goal.carbohydrates else 0,
            }

            data = {
                'date': target_date,
                'daily_goal': DailyGoalSerializer(daily_goal).data,
                'total_consumed': {
                    'calories': float(total_calories),
                    'protein': float(total_protein),
                    'fat': float(total_fat),
                    'carbohydrates': float(total_carbs),
                },
                'progress': progress,
                'meals': MealSerializer(meals, many=True).data,
            }

            return Response(data)
        else:
            # Return simple list of meals
            return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Создать новый приём пищи",
        description="Создаёт новый приём пищи (завтрак, обед, ужин или перекус).",
        request=MealCreateSerializer,
        responses={
            201: MealSerializer,
            400: OpenApiResponse(description="Невалидные данные"),
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


@extend_schema(tags=['Meals'])
class MealDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/v1/meals/{id}/
    """

    permission_classes = [IsAuthenticated]
    serializer_class = MealSerializer

    def get_queryset(self):
        return Meal.objects.filter(user=self.request.user).prefetch_related('items')

    @extend_schema(
        summary="Получить детали приёма пищи",
        description="Возвращает детальную информацию о приёме пищи со всеми блюдами.",
        responses={
            200: MealSerializer,
            404: OpenApiResponse(description="Приём пищи не найден"),
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить приём пищи",
        description="Обновляет информацию о приёме пищи (тип или дату).",
        request=MealCreateSerializer,
        responses={
            200: MealSerializer,
            400: OpenApiResponse(description="Невалидные данные"),
            404: OpenApiResponse(description="Приём пищи не найден"),
        }
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить приём пищи",
        description="Частично обновляет информацию о приёме пищи.",
        request=MealCreateSerializer,
        responses={
            200: MealSerializer,
            400: OpenApiResponse(description="Невалидные данные"),
            404: OpenApiResponse(description="Приём пищи не найден"),
        }
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить приём пищи",
        description="Удаляет приём пищи и все связанные блюда.",
        responses={
            204: OpenApiResponse(description="Приём пищи успешно удалён"),
            404: OpenApiResponse(description="Приём пищи не найден"),
        }
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


@extend_schema(tags=['Food Items'])
class FoodItemCreateView(generics.CreateAPIView):
    """
    POST /api/v1/meals/{meal_id}/items/ - Add food item to meal

    Nested resource: creates food item within specific meal.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = FoodItemSerializer

    @extend_schema(
        summary="Добавить блюдо в приём пищи",
        description="Создаёт новое блюдо и добавляет его в указанный приём пищи.",
        request=FoodItemSerializer,
        responses={
            201: FoodItemSerializer,
            400: OpenApiResponse(description="Невалидные данные"),
            404: OpenApiResponse(description="Приём пищи не найден"),
        }
    )
    def post(self, request, meal_id, *args, **kwargs):
        # Verify meal exists and belongs to user
        meal = get_object_or_404(Meal, id=meal_id, user=request.user)

        # Create food item
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(meal=meal)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Food Items'])
class FoodItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PUT/PATCH/DELETE /api/v1/meals/{meal_id}/items/{id}/

    Nested resource: manages specific food item within meal.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = FoodItemSerializer

    def get_queryset(self):
        meal_id = self.kwargs.get('meal_id')
        # First verify that meal belongs to current user
        meal = get_object_or_404(Meal, id=meal_id, user=self.request.user)
        # Then return food items only from this verified meal
        return FoodItem.objects.filter(meal=meal)

    @extend_schema(
        summary="Получить детали блюда",
        description="Возвращает детальную информацию о блюде.",
        responses={
            200: FoodItemSerializer,
            404: OpenApiResponse(description="Блюдо не найдено"),
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить блюдо",
        description="Обновляет информацию о блюде (название, вес, КБЖУ).",
        request=FoodItemSerializer,
        responses={
            200: FoodItemSerializer,
            400: OpenApiResponse(description="Невалидные данные"),
            404: OpenApiResponse(description="Блюдо не найдено"),
        }
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Частично обновить блюдо",
        description="Частично обновляет информацию о блюде.",
        request=FoodItemSerializer,
        responses={
            200: FoodItemSerializer,
            400: OpenApiResponse(description="Невалидные данные"),
            404: OpenApiResponse(description="Блюдо не найдено"),
        }
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(
        summary="Удалить блюдо",
        description="Удаляет блюдо из приёма пищи.",
        responses={
            204: OpenApiResponse(description="Блюдо успешно удалено"),
            404: OpenApiResponse(description="Блюдо не найдено"),
        }
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


@extend_schema(tags=['Nutrition - Daily Goals'])
class DailyGoalView(generics.RetrieveUpdateAPIView):
    """
    Get or update current daily goal.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DailyGoalSerializer

    def get_object(self):
        """Get active daily goal for current user."""
        try:
            return DailyGoal.objects.get(user=self.request.user, is_active=True)
        except DailyGoal.DoesNotExist:
            return None

    @extend_schema(
        summary="Получить текущую дневную цель",
        description="Возвращает активную дневную цель КБЖУ для пользователя.",
        responses={
            200: DailyGoalSerializer,
            404: OpenApiResponse(description="Дневная цель не установлена"),
        }
    )
    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj is None:
            return Response(
                {"error": "Дневная цель не установлена"},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

    @extend_schema(
        summary="Обновить дневную цель (полностью)",
        description="Полностью обновляет дневную цель КБЖУ.",
        request=DailyGoalSerializer,
        responses={
            200: DailyGoalSerializer,
            400: OpenApiResponse(description="Невалидные данные"),
        }
    )
    def put(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj is None:
            # Create new goal if none exists
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return super().put(request, *args, **kwargs)

    @extend_schema(
        summary="Обновить дневную цель (частично)",
        description="Частично обновляет дневную цель КБЖУ.",
        request=DailyGoalSerializer,
        responses={
            200: DailyGoalSerializer,
            400: OpenApiResponse(description="Невалидные данные"),
        }
    )
    def patch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj is None:
            # Create new goal if none exists
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return super().patch(request, *args, **kwargs)


@extend_schema(tags=['Nutrition - Daily Goals'])
class CalculateGoalsView(views.APIView):
    """
    Calculate daily goals using Mifflin-St Jeor formula based on user profile.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = CalculateGoalsSerializer

    @extend_schema(
        summary="Рассчитать дневную цель по профилю",
        description="Автоматически рассчитывает дневную цель КБЖУ на основе данных профиля пользователя (пол, возраст, рост, вес, активность) используя формулу Mifflin-St Jeor.",
        responses={
            200: CalculateGoalsSerializer,
            400: OpenApiResponse(description="Не заполнен профиль или недостаточно данных"),
        }
    )
    def post(self, request):
        try:
            goals = DailyGoal.calculate_goals(request.user)
            return Response(goals)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema(tags=['Nutrition - Daily Goals'])
class SetAutoGoalView(views.APIView):
    """
    Calculate and set daily goal automatically.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DailyGoalSerializer

    @extend_schema(
        summary="Установить автоматическую дневную цель",
        description="Рассчитывает и устанавливает дневную цель КБЖУ на основе профиля пользователя.",
        responses={
            201: DailyGoalSerializer,
            400: OpenApiResponse(description="Не заполнен профиль или недостаточно данных"),
        }
    )
    def post(self, request):
        try:
            goals = DailyGoal.calculate_goals(request.user)

            # Create new daily goal with calculated values
            daily_goal = DailyGoal.objects.create(
                user=request.user,
                calories=goals['calories'],
                protein=goals['protein'],
                fat=goals['fat'],
                carbohydrates=goals['carbohydrates'],
                source='AUTO',
                is_active=True
            )

            serializer = DailyGoalSerializer(daily_goal)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
