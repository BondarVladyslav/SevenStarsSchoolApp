from django.contrib.auth import get_user_model
from django.test import TestCase

from courses.models import Group, Level, Subject
from moderation.forms import (
    GroupEditForm,
    LevelEditForm,
    ParentEditForm,
    StudentEditForm,
    SubjectEditForm,
    TeacherEditForm,
)
from users.models import Parent, Student, Teacher

User = get_user_model()


class StudentEditFormTests(TestCase):
    def test_prefills_first_and_last_name_from_user(self):
        user = User.objects.create_user(
            username='student1', password='pass12345', first_name='Іван', last_name='Петров',
        )
        student = Student.objects.create(user=user)

        form = StudentEditForm(instance=student)

        self.assertEqual(form.fields['first_name'].initial, 'Іван')
        self.assertEqual(form.fields['last_name'].initial, 'Петров')

    def test_save_updates_user_names(self):
        user = User.objects.create_user(username='student2', password='pass12345')
        student = Student.objects.create(user=user)

        form = StudentEditForm(data={'first_name': 'Марія', 'last_name': 'Іванова'}, instance=student)
        self.assertTrue(form.is_valid())
        form.save()

        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Марія')
        self.assertEqual(user.last_name, 'Іванова')

    def test_requires_first_and_last_name(self):
        form = StudentEditForm(data={'first_name': '', 'last_name': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)
        self.assertIn('last_name', form.errors)


class ParentEditFormTests(TestCase):
    def test_save_updates_user_names(self):
        user = User.objects.create_user(username='parent1', password='pass12345')
        parent = Parent.objects.create(user=user)

        form = ParentEditForm(data={'first_name': 'Олена', 'last_name': 'Сидорова'}, instance=parent)
        self.assertTrue(form.is_valid())
        form.save()

        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Олена')
        self.assertEqual(user.last_name, 'Сидорова')


class TeacherEditFormTests(TestCase):
    def test_save_updates_names_and_group_assignments(self):
        user = User.objects.create_user(username='teacher1', password='pass12345')
        teacher = Teacher.objects.create(user=user)
        subject = Subject.objects.create(name='Математика')
        group1 = Group.objects.create(name='Group 1', subject=subject)
        group2 = Group.objects.create(name='Group 2', subject=subject)

        form = TeacherEditForm(
            data={'first_name': 'Петро', 'last_name': 'Іванов', 'groups': [group1.id, group2.id]},
            instance=teacher,
        )
        self.assertTrue(form.is_valid())
        form.save()

        group1.refresh_from_db()
        group2.refresh_from_db()
        self.assertEqual(group1.teacher, teacher)
        self.assertEqual(group2.teacher, teacher)

    def test_save_removes_groups_not_selected_anymore(self):
        user = User.objects.create_user(username='teacher2', password='pass12345')
        teacher = Teacher.objects.create(user=user)
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group 1', subject=subject, teacher=teacher)

        form = TeacherEditForm(
            data={'first_name': 'Петро', 'last_name': 'Іванов', 'groups': []},
            instance=teacher,
        )
        self.assertTrue(form.is_valid())
        form.save()

        group.refresh_from_db()
        self.assertIsNone(group.teacher)

    def test_groups_field_prefilled_from_instance(self):
        user = User.objects.create_user(username='teacher3', password='pass12345')
        teacher = Teacher.objects.create(user=user)
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group 1', subject=subject, teacher=teacher)

        form = TeacherEditForm(instance=teacher)

        self.assertIn(group, form.fields['groups'].initial)


class GroupEditFormTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='teacher1', password='pass12345')
        self.teacher = Teacher.objects.create(user=user)
        self.subject = Subject.objects.create(name='Математика')
        self.other_subject = Subject.objects.create(name='Фізика')
        self.level = Level.objects.create(subject=self.subject, name='Beginner')

    def test_valid_group_data(self):
        form = GroupEditForm(data={
            'name': 'Group A',
            'teacher': self.teacher.id,
            'subject': self.subject.id,
            'level': self.level.id,
        })
        self.assertTrue(form.is_valid())

    def test_level_must_belong_to_selected_subject(self):
        form = GroupEditForm(data={
            'name': 'Group A',
            'teacher': self.teacher.id,
            'subject': self.other_subject.id,
            'level': self.level.id,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('level', form.errors)

    def test_level_is_optional(self):
        form = GroupEditForm(data={
            'name': 'Group A',
            'teacher': self.teacher.id,
            'subject': self.subject.id,
            'level': '',
        })
        self.assertTrue(form.is_valid())

    def test_subject_is_required(self):
        form = GroupEditForm(data={
            'name': 'Group A',
            'teacher': self.teacher.id,
            'subject': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('subject', form.errors)


class SubjectEditFormTests(TestCase):
    def test_valid_with_name(self):
        form = SubjectEditForm(data={'name': 'Хімія'})
        self.assertTrue(form.is_valid())

    def test_invalid_without_name(self):
        form = SubjectEditForm(data={'name': ''})
        self.assertFalse(form.is_valid())


class LevelEditFormTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')

    def test_valid_level_data(self):
        form = LevelEditForm(data={'subject': self.subject.id, 'name': 'Advanced', 'order': 1})
        self.assertTrue(form.is_valid())

    def test_subject_is_required(self):
        form = LevelEditForm(data={'subject': '', 'name': 'Advanced', 'order': 1})
        self.assertFalse(form.is_valid())
        self.assertIn('subject', form.errors)
