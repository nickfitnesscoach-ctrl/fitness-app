"""
Tests for Telegram app - Personal Plan API endpoints.
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from .models import TelegramUser, PersonalPlanSurvey, PersonalPlan


class PersonalPlanAPITestCase(TestCase):
    """Test cases for Personal Plan API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            username='tg_123456789',
            email='test_123456789@telegram.bot',
            first_name='Test User'
        )

        # Create TelegramUser
        self.telegram_user = TelegramUser.objects.create(
            user=self.user,
            telegram_id=123456789,
            username='testuser',
            first_name='Test',
            last_name='User'
        )

    def test_get_user_or_create_existing(self):
        """Test getting an existing user."""
        url = reverse('telegram-user-get-or-create')
        response = self.client.get(url, {
            'telegram_id': 123456789,
            'username': 'testuser',
            'full_name': 'Test User'
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['telegram_id'], 123456789)
        self.assertEqual(response.data['created'], False)

    def test_get_user_or_create_new(self):
        """Test creating a new user."""
        url = reverse('telegram-user-get-or-create')
        response = self.client.get(url, {
            'telegram_id': 987654321,
            'username': 'newuser',
            'full_name': 'New User'
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['telegram_id'], 987654321)
        self.assertEqual(response.data['created'], True)

        # Check user was created
        self.assertTrue(
            TelegramUser.objects.filter(telegram_id=987654321).exists()
        )

    def test_get_user_or_create_missing_telegram_id(self):
        """Test error when telegram_id is missing."""
        url = reverse('telegram-user-get-or-create')
        response = self.client.get(url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_create_survey(self):
        """Test creating a survey."""
        url = reverse('personal-plan-create-survey')
        data = {
            'telegram_id': 123456789,
            'gender': 'male',
            'age': 30,
            'height_cm': 180,
            'weight_kg': 80.5,
            'target_weight_kg': 75.0,
            'activity': 'moderate',
            'training_level': 'intermediate',
            'body_goals': ['weight_loss'],
            'health_limitations': [],
            'body_now_id': 2,
            'body_now_label': 'Athletic',
            'body_now_file': 'body_2.png',
            'body_ideal_id': 3,
            'body_ideal_label': 'Fit',
            'body_ideal_file': 'body_3.png',
            'timezone': 'Europe/Moscow',
            'utc_offset_minutes': 180
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['gender'], 'male')
        self.assertEqual(response.data['age'], 30)

        # Check survey was created
        self.assertEqual(PersonalPlanSurvey.objects.count(), 1)
        survey = PersonalPlanSurvey.objects.first()
        self.assertEqual(survey.user, self.user)

    def test_create_survey_invalid_data(self):
        """Test creating survey with invalid data."""
        url = reverse('personal-plan-create-survey')
        data = {
            'telegram_id': 123456789,
            'gender': 'invalid',  # Invalid choice
            'age': 30,
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_plan(self):
        """Test creating a personal plan."""
        # First create a survey
        survey = PersonalPlanSurvey.objects.create(
            user=self.user,
            gender='male',
            age=30,
            height_cm=180,
            weight_kg=80.5,
            activity='moderate',
            body_now_id=2,
            body_now_file='body_2.png',
            body_ideal_id=3,
            body_ideal_file='body_3.png',
            timezone='Europe/Moscow',
            utc_offset_minutes=180
        )

        url = reverse('personal-plan-create-plan')
        data = {
            'telegram_id': 123456789,
            'survey_id': survey.id,
            'ai_text': 'Your personal plan...',
            'ai_model': 'gpt-4',
            'prompt_version': 'v1.0'
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['ai_text'], 'Your personal plan...')

        # Check plan was created
        self.assertEqual(PersonalPlan.objects.count(), 1)
        plan = PersonalPlan.objects.first()
        self.assertEqual(plan.user, self.user)
        self.assertEqual(plan.survey, survey)

    def test_create_plan_user_not_found(self):
        """Test creating plan for non-existent user."""
        url = reverse('personal-plan-create-plan')
        data = {
            'telegram_id': 999999999,
            'ai_text': 'Your personal plan...',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_plan_daily_limit(self):
        """Test daily limit for creating plans."""
        url = reverse('personal-plan-create-plan')

        # Create 3 plans (max limit)
        for i in range(3):
            PersonalPlan.objects.create(
                user=self.user,
                ai_text=f'Plan {i}'
            )

        # Try to create 4th plan
        data = {
            'telegram_id': 123456789,
            'ai_text': 'Your personal plan...',
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('Daily limit', response.data['error'])

    def test_count_plans_today(self):
        """Test counting plans created today."""
        # Create 2 plans
        PersonalPlan.objects.create(user=self.user, ai_text='Plan 1')
        PersonalPlan.objects.create(user=self.user, ai_text='Plan 2')

        url = reverse('personal-plan-count-today')
        response = self.client.get(url, {'telegram_id': 123456789})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(response.data['limit'], 3)
        self.assertEqual(response.data['can_create'], True)

    def test_count_plans_today_user_not_found(self):
        """Test counting plans for non-existent user - should return count=0, can_create=true."""
        url = reverse('personal-plan-count-today')
        response = self.client.get(url, {'telegram_id': 999999999})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['limit'], 3)
        self.assertEqual(response.data['can_create'], True)

    def test_count_plans_today_missing_telegram_id(self):
        """Test counting plans without telegram_id."""
        url = reverse('personal-plan-count-today')
        response = self.client.get(url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('telegram_id is required', response.data['error'])

    def test_count_plans_today_invalid_telegram_id(self):
        """Test counting plans with invalid telegram_id (not an integer)."""
        url = reverse('personal-plan-count-today')
        response = self.client.get(url, {'telegram_id': 'invalid_id'})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid telegram_id', response.data['error'])

    def test_count_plans_today_limit_reached(self):
        """Test counting plans when daily limit is reached."""
        # Create 3 plans (the limit)
        for i in range(3):
            PersonalPlan.objects.create(
                user=self.user,
                ai_text=f'Plan {i + 1}'
            )

        url = reverse('personal-plan-count-today')
        response = self.client.get(url, {'telegram_id': 123456789})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(response.data['limit'], 3)
        self.assertEqual(response.data['can_create'], False)
