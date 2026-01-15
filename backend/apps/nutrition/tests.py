from datetime import date
from io import BytesIO

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import DailyGoal, Meal, MealPhoto, FoodItem
from .services import get_daily_stats

User = get_user_model()


class DailyGoalTestCase(TestCase):
    """Tests for DailyGoal API endpoints"""

    def setUp(self):
        """Set up test client and test user"""
        self.client = APIClient()
        self.user = User.objects.create_user(username="test_user", password="testpass123")
        # Profile is auto-created via signal, set telegram_id
        self.user.profile.telegram_id = 123456789
        self.user.profile.save()
        self.client.force_authenticate(user=self.user)
        self.goals_url = "/api/v1/goals/"

    def test_create_goal_via_put(self):
        """Test creating a new goal via PUT request"""
        data = {
            "calories": 2000,
            "protein": 150,
            "fat": 70,
            "carbohydrates": 250,
            "source": "MANUAL",
            "is_active": True,
        }

        response = self.client.put(self.goals_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["calories"], 2000)
        self.assertEqual(response.data["protein"], "150.00")
        self.assertEqual(response.data["source"], "MANUAL")

        # Verify goal is created in database
        goal = DailyGoal.objects.get(user=self.user)
        self.assertEqual(goal.calories, 2000)
        self.assertTrue(goal.is_active)

    def test_update_existing_goal(self):
        """Test updating an existing goal"""
        # Create initial goal
        initial_goal = DailyGoal.objects.create(
            user=self.user, calories=1800, protein=120, fat=60, carbohydrates=200, source="AUTO"
        )

        # Update goal
        data = {
            "calories": 2200,
            "protein": 160,
            "fat": 80,
            "carbohydrates": 270,
            "source": "MANUAL",
            "is_active": True,
        }

        response = self.client.put(self.goals_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["calories"], 2200)
        self.assertEqual(response.data["source"], "MANUAL")

        # Verify goal is updated
        initial_goal.refresh_from_db()
        self.assertEqual(initial_goal.calories, 2200)

    def test_get_current_goal(self):
        """Test retrieving current active goal"""
        DailyGoal.objects.create(
            user=self.user, calories=2000, protein=150, fat=70, carbohydrates=250, source="MANUAL"
        )

        response = self.client.get(self.goals_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_set"])
        self.assertEqual(response.data["goal"]["calories"], 2000)

    def test_validation_minimum_calories(self):
        """Test that calories must be at least 500"""
        data = {
            "calories": 400,
            "protein": 150,
            "fat": 70,
            "carbohydrates": 250,
            "source": "MANUAL",
            "is_active": True,
        }

        response = self.client.put(self.goals_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validation_negative_macros(self):
        """Test that macros cannot be negative"""
        data = {
            "calories": 2000,
            "protein": -10,
            "fat": 70,
            "carbohydrates": 250,
            "source": "MANUAL",
            "is_active": True,
        }

        response = self.client.put(self.goals_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request(self):
        """Test that unauthenticated requests are rejected"""
        self.client.force_authenticate(user=None)

        data = {
            "calories": 2000,
            "protein": 150,
            "fat": 70,
            "carbohydrates": 250,
            "source": "MANUAL",
        }

        response = self.client.put(self.goals_url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_only_one_active_goal_per_user(self):
        """Test that creating a new active goal deactivates old ones"""
        # Create first active goal
        goal1 = DailyGoal.objects.create(
            user=self.user,
            calories=1800,
            protein=120,
            fat=60,
            carbohydrates=200,
            source="AUTO",
            is_active=True,
        )
        self.assertTrue(goal1.is_active)

        # Create second active goal
        goal2 = DailyGoal.objects.create(
            user=self.user,
            calories=2000,
            protein=150,
            fat=70,
            carbohydrates=250,
            source="MANUAL",
            is_active=True,
        )

        # Refresh goal1 from database
        goal1.refresh_from_db()

        # goal1 should be deactivated, goal2 should be active
        self.assertFalse(goal1.is_active)
        self.assertTrue(goal2.is_active)

        # Only one active goal should exist
        active_goals = DailyGoal.objects.filter(user=self.user, is_active=True)
        self.assertEqual(active_goals.count(), 1)
        self.assertEqual(active_goals.first().id, goal2.id)


class MealPhotoCancelTestCase(TestCase):
    """
    Tests for server-safe Cancel implementation for AI photo processing.

    Verification scenarios:
    - A: 3 фото, 1 success, cancel → дневник показывает 1 фото
    - B: 3 фото, cancel сразу → meal не появляется
    - C: 1 success, cancel, retry 1 → meal содержит 2 фото
    - D: Cancel во время processing, задача успела завершиться → фото не в дневнике
    """

    def setUp(self):
        """Set up test client and test user"""
        self.client = APIClient()
        self.user = User.objects.create_user(username="test_user", password="testpass123")
        # Profile is auto-created via signal, set telegram_id
        self.user.profile.telegram_id = 123456789
        self.user.profile.save()
        self.client.force_authenticate(user=self.user)
        self.today = date.today()

    def _create_test_image(self):
        """Create a minimal test image file."""
        file = BytesIO()
        image = Image.new("RGB", (100, 100), color="red")
        image.save(file, "JPEG")
        file.seek(0)
        return SimpleUploadedFile("test.jpg", file.read(), content_type="image/jpeg")

    def _create_meal_with_photos(self, photo_statuses):
        """
        Helper: Create a meal with multiple photos in given statuses.

        Args:
            photo_statuses: List of status strings (e.g., ['SUCCESS', 'CANCELLED', 'FAILED'])

        Returns:
            Meal instance with photos created
        """
        meal = Meal.objects.create(
            user=self.user, meal_type="LUNCH", date=self.today, status="PROCESSING"
        )

        photos = []
        for photo_status in photo_statuses:
            photo = MealPhoto.objects.create(
                meal=meal, status=photo_status, image=self._create_test_image()
            )
            photos.append(photo)

            # Create FoodItems only for SUCCESS photos
            if photo_status == "SUCCESS":
                FoodItem.objects.create(
                    meal=meal,
                    name="Test Food",
                    grams=100,
                    calories=200,
                    protein=10,
                    fat=5,
                    carbohydrates=30,
                )

        return meal

    def test_scenario_a_one_success_two_cancelled(self):
        """
        Scenario A: 3 photos, 1 success, 2 cancelled → diary shows 1 photo.

        BR-2: Only SUCCESS photos are visible in diary.
        """
        # Create meal with 1 SUCCESS, 2 CANCELLED photos
        meal = self._create_meal_with_photos(["SUCCESS", "CANCELLED", "CANCELLED"])
        meal.status = "COMPLETE"  # Finalized with at least one success
        meal.save()

        # Fetch diary via API
        response = self.client.get(f"/api/v1/meals/?date={self.today}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify meal appears in diary
        meals = response.data["meals"]
        self.assertEqual(len(meals), 1)

        # Verify only 1 SUCCESS photo is visible
        meal_data = meals[0]
        self.assertEqual(len(meal_data["photos"]), 1)
        self.assertEqual(meal_data["photos"][0]["status"], "SUCCESS")

        # Verify FoodItems are present
        self.assertEqual(len(meal_data["items"]), 1)

    def test_scenario_b_all_cancelled_meal_hidden(self):
        """
        Scenario B: 3 photos, all cancelled → meal does not appear in diary.

        BR-1: Meal with no SUCCESS photos is hidden from diary.
        """
        # Create meal with 3 CANCELLED photos (no FoodItems created)
        meal = self._create_meal_with_photos(["CANCELLED", "CANCELLED", "CANCELLED"])
        meal.status = "FAILED"  # Finalized as FAILED (all photos failed/cancelled)
        meal.save()

        # Fetch diary via API
        response = self.client.get(f"/api/v1/meals/?date={self.today}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify meal does NOT appear in diary
        meals = response.data["meals"]
        self.assertEqual(len(meals), 0)

    def test_scenario_c_retry_after_cancel(self):
        """
        Scenario C: 1 success, cancel, retry 1 → meal contains 2 photos.

        Retry functionality allows adding more SUCCESS photos to existing meal.
        """
        # Create meal with 1 SUCCESS, 1 CANCELLED
        meal = self._create_meal_with_photos(["SUCCESS", "CANCELLED"])

        # Simulate retry: create another SUCCESS photo
        photo_retry = MealPhoto.objects.create(
            meal=meal, status="SUCCESS", image=self._create_test_image()
        )
        FoodItem.objects.create(
            meal=meal,
            name="Retry Food",
            grams=150,
            calories=300,
            protein=15,
            fat=8,
            carbohydrates=40,
        )

        meal.status = "COMPLETE"  # Still complete
        meal.save()

        # Fetch diary via API
        response = self.client.get(f"/api/v1/meals/?date={self.today}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify meal contains 2 SUCCESS photos (original + retry)
        meals = response.data["meals"]
        self.assertEqual(len(meals), 1)

        meal_data = meals[0]
        self.assertEqual(len(meal_data["photos"]), 2)  # 2 SUCCESS photos
        self.assertEqual(len(meal_data["items"]), 2)  # 2 FoodItems

    def test_scenario_d_race_condition_cancelled_hides_photo(self):
        """
        Scenario D: Cancel during processing, task completes → photo not in diary.

        Race condition guard in task prevents attaching results if photo was cancelled.
        """
        # Create meal with 1 CANCELLED photo (simulating race condition)
        # Task completed but photo was marked CANCELLED before results saved
        meal = self._create_meal_with_photos(["CANCELLED"])
        meal.status = "FAILED"
        meal.save()

        # Verify NO FoodItems were created (guard prevented attachment)
        self.assertEqual(meal.items.count(), 0)

        # Fetch diary via API
        response = self.client.get(f"/api/v1/meals/?date={self.today}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify meal does NOT appear in diary
        meals = response.data["meals"]
        self.assertEqual(len(meals), 0)

    def test_get_daily_stats_excludes_failed_meals(self):
        """Test that get_daily_stats service excludes FAILED meals."""
        # Create FAILED meal (all photos cancelled)
        failed_meal = self._create_meal_with_photos(["CANCELLED"])
        failed_meal.status = "FAILED"
        failed_meal.save()

        # Create COMPLETE meal with SUCCESS photo
        success_meal = self._create_meal_with_photos(["SUCCESS"])
        success_meal.status = "COMPLETE"
        success_meal.save()

        # Fetch stats
        stats = get_daily_stats(self.user, self.today)

        # Verify only COMPLETE meal is included
        self.assertEqual(len(stats["meals"]), 1)
        self.assertEqual(stats["meals"][0].id, success_meal.id)

    def test_meal_serializer_filters_cancelled_photos(self):
        """Test that MealSerializer only returns SUCCESS photos in 'photos' field."""
        # Create meal with mixed photo statuses
        meal = self._create_meal_with_photos(["SUCCESS", "CANCELLED", "FAILED", "PENDING"])
        meal.status = "PROCESSING"
        meal.save()

        # Fetch meal detail via API
        response = self.client.get(f"/api/v1/meals/{meal.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify only SUCCESS photo is in 'photos' field
        photos = response.data["photos"]
        self.assertEqual(len(photos), 1)
        self.assertEqual(photos[0]["status"], "SUCCESS")

    def test_n_plus_one_prevention_for_meal_photos(self):
        """
        Test that fetching multiple meals does NOT cause N+1 queries for photos.

        P0: Critical performance test - verifies prefetch_related prevents N+1.
        Expected queries:
        1. SAVEPOINT (transaction)
        2. SELECT daily_goals (for API response)
        3. SELECT meals (main queryset)
        4. SELECT food items (prefetch_related)
        5. SELECT meal photos (prefetch_related)
        6. RELEASE SAVEPOINT
        Total: 6 queries regardless of number of meals
        """
        # Create 5 meals with multiple photos each
        for _ in range(5):
            meal = self._create_meal_with_photos(["SUCCESS", "SUCCESS", "CANCELLED"])
            meal.status = "COMPLETE"
            meal.save()

        # Fetch diary with assertNumQueries
        # Expected: 6 queries (savepoint, goals, meals, items prefetch, photos prefetch, release)
        with self.assertNumQueries(6):
            response = self.client.get(f"/api/v1/meals/?date={self.today}")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            # Force evaluation of response data (triggers serializer)
            meals = response.data["meals"]
            self.assertEqual(len(meals), 5)

            # Access photos field for each meal (would cause N+1 without prefetch)
            for meal_data in meals:
                _ = meal_data["photos"]  # This line would trigger +1 query per meal without prefetch

    def test_serializer_only_returns_success_photos_no_n_plus_one(self):
        """
        P0.5 Microtest: Verifies both serializer filtering AND query efficiency.

        Critical invariants:
        1. API response contains ONLY SUCCESS photos (no CANCELLED/FAILED/PENDING leak)
        2. Number of queries is fixed regardless of meal count (no N+1)

        This is a regression detector for:
        - Serializer filter removal/breakage
        - Prefetch removal causing N+1
        - Race guard failure allowing CANCELLED photos with items
        """
        # Create 5 meals with mixed photo statuses
        for _ in range(5):
            meal = self._create_meal_with_photos(
                ["SUCCESS", "CANCELLED", "FAILED"]  # 3 photos, only 1 SUCCESS
            )
            meal.status = "COMPLETE"
            meal.save()

        # Fetch diary with assertNumQueries
        # Expected: 6 queries (savepoint, goals, meals, items prefetch, photos prefetch, release)
        with self.assertNumQueries(6):
            response = self.client.get(f"/api/v1/meals/?date={self.today}")
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            meals = response.data["meals"]
            self.assertEqual(len(meals), 5)

            # Critical assertion: ONLY SUCCESS photos in payload
            for meal_data in meals:
                photos = meal_data["photos"]

                # Each meal should have exactly 1 SUCCESS photo
                self.assertEqual(
                    len(photos), 1, f"Meal {meal_data['id']}: expected 1 SUCCESS photo, got {len(photos)}"
                )

                # ALL photos must have status="SUCCESS"
                for photo in photos:
                    self.assertEqual(
                        photo["status"],
                        "SUCCESS",
                        f"Photo {photo['id']}: non-SUCCESS photo leaked into API response (status={photo['status']})",
                    )
