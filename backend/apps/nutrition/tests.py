from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import DailyGoal

User = get_user_model()


class DailyGoalTestCase(TestCase):
    """Tests for DailyGoal API endpoints"""

    def setUp(self):
        """Set up test client and test user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            telegram_id=123456789,
            username='test_user'
        )
        self.client.force_authenticate(user=self.user)
        self.goals_url = '/api/v1/goals/'

    def test_create_goal_via_put(self):
        """Test creating a new goal via PUT request"""
        data = {
            'calories': 2000,
            'protein': 150,
            'fat': 70,
            'carbohydrates': 250,
            'source': 'MANUAL',
            'is_active': True
        }

        response = self.client.put(self.goals_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['calories'], 2000)
        self.assertEqual(response.data['protein'], '150.0')
        self.assertEqual(response.data['source'], 'MANUAL')

        # Verify goal is created in database
        goal = DailyGoal.objects.get(user=self.user)
        self.assertEqual(goal.calories, 2000)
        self.assertTrue(goal.is_active)

    def test_update_existing_goal(self):
        """Test updating an existing goal"""
        # Create initial goal
        initial_goal = DailyGoal.objects.create(
            user=self.user,
            calories=1800,
            protein=120,
            fat=60,
            carbohydrates=200,
            source='AUTO'
        )

        # Update goal
        data = {
            'calories': 2200,
            'protein': 160,
            'fat': 80,
            'carbohydrates': 270,
            'source': 'MANUAL',
            'is_active': True
        }

        response = self.client.put(self.goals_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['calories'], 2200)
        self.assertEqual(response.data['source'], 'MANUAL')

        # Verify goal is updated
        initial_goal.refresh_from_db()
        self.assertEqual(initial_goal.calories, 2200)

    def test_get_current_goal(self):
        """Test retrieving current active goal"""
        DailyGoal.objects.create(
            user=self.user,
            calories=2000,
            protein=150,
            fat=70,
            carbohydrates=250,
            source='MANUAL'
        )

        response = self.client.get(self.goals_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['calories'], 2000)

    def test_validation_minimum_calories(self):
        """Test that calories must be at least 500"""
        data = {
            'calories': 400,
            'protein': 150,
            'fat': 70,
            'carbohydrates': 250,
            'source': 'MANUAL',
            'is_active': True
        }

        response = self.client.put(self.goals_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validation_negative_macros(self):
        """Test that macros cannot be negative"""
        data = {
            'calories': 2000,
            'protein': -10,
            'fat': 70,
            'carbohydrates': 250,
            'source': 'MANUAL',
            'is_active': True
        }

        response = self.client.put(self.goals_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request(self):
        """Test that unauthenticated requests are rejected"""
        self.client.force_authenticate(user=None)

        data = {
            'calories': 2000,
            'protein': 150,
            'fat': 70,
            'carbohydrates': 250,
            'source': 'MANUAL'
        }

        response = self.client.put(self.goals_url, data, format='json')

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
            source='AUTO',
            is_active=True
        )
        self.assertTrue(goal1.is_active)

        # Create second active goal
        goal2 = DailyGoal.objects.create(
            user=self.user,
            calories=2000,
            protein=150,
            fat=70,
            carbohydrates=250,
            source='MANUAL',
            is_active=True
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
