from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from courses.models import Group, Subject
from moderation.views import (
    create_user_with_unique_username,
    generate_password,
    generate_username,
    get_nearby_lesson_occurrences,
)
from schedule.models import Lesson, ScheduleException

User = get_user_model()


class GenerateUsernameTests(TestCase):
    def test_generates_dotted_lowercase_username(self):
        username = generate_username('Іван', 'Петров')
        self.assertEqual(username, 'іван.петров')

    def test_appends_counter_on_collision(self):
        User.objects.create_user(username='john.doe', password='pass12345')
        username = generate_username('John', 'Doe')
        self.assertEqual(username, 'john.doe1')

    def test_increments_counter_for_multiple_collisions(self):
        User.objects.create_user(username='john.doe', password='pass12345')
        User.objects.create_user(username='john.doe1', password='pass12345')
        username = generate_username('John', 'Doe')
        self.assertEqual(username, 'john.doe2')


class CreateUserWithUniqueUsernameTests(TestCase):
    def test_creates_user_with_working_password(self):
        user = create_user_with_unique_username('Andrii', 'Kovalenko', 'strongpass1')
        self.assertTrue(user.check_password('strongpass1'))
        self.assertEqual(user.username, 'andrii.kovalenko')

    def test_avoids_duplicate_usernames(self):
        User.objects.create_user(username='john.doe', password='12345678')
        user = create_user_with_unique_username('John', 'Doe', '12345678')
        self.assertEqual(user.username, 'john.doe1')
        self.assertTrue(User.objects.filter(username='john.doe1').exists())


class GeneratePasswordTests(TestCase):
    def test_default_length_is_ten(self):
        password = generate_password()
        self.assertEqual(len(password), 10)

    def test_custom_length(self):
        password = generate_password(20)
        self.assertEqual(len(password), 20)

    def test_passwords_are_random(self):
        passwords = {generate_password() for _ in range(20)}
        self.assertGreater(len(passwords), 1)


class GetNearbyLessonOccurrencesTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.group = Group.objects.create(name='Group A', subject=subject)

    def test_occurrences_include_lessons_within_range(self):
        today = timezone.localdate()
        lesson = Lesson.objects.create(
            group=self.group, weekday=today.weekday(), start_time=time(10, 0), end_time=time(11, 0),
        )

        occurrences = get_nearby_lesson_occurrences(self.group, days_range=5)

        matching = [o for o in occurrences if o['lesson'] == lesson and o['date'] == today]
        self.assertEqual(len(matching), 1)

    def test_cancelled_occurrence_is_excluded(self):
        today = timezone.localdate()
        lesson = Lesson.objects.create(
            group=self.group, weekday=today.weekday(), start_time=time(10, 0), end_time=time(11, 0),
        )
        ScheduleException.objects.create(
            lesson=lesson, original_date=today, exception_type='cancelled',
        )

        occurrences = get_nearby_lesson_occurrences(self.group, days_range=5)

        matching = [o for o in occurrences if o['lesson'] == lesson and o['date'] == today]
        self.assertEqual(len(matching), 0)
