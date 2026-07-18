from django.contrib.auth import get_user_model
from django.test import TestCase

from courses.models import Group, Level, Subject
from materials.models import Material
from materials.utils import (
    get_all_materials_grouped,
    get_materials_by_group,
    user_has_access_to_material,
)
from users.models import Student, Teacher

User = get_user_model()


class GetMaterialsByGroupTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')
        self.level = Level.objects.create(subject=self.subject, name='Beginner')
        self.group = Group.objects.create(name='Group A', subject=self.subject, level=self.level)

    def test_returns_materials_matching_subject_and_level(self):
        material = Material.objects.create(subject=self.subject, level=self.level, title='Тема 1')
        Material.objects.create(subject=self.subject, title='Не той рівень', level=None)

        other_subject = Subject.objects.create(name='Фізика')
        Material.objects.create(subject=other_subject, title='Інший предмет')

        sections = get_materials_by_group([self.group.id])

        self.assertEqual(len(sections), 1)
        materials_in_section = list(sections[0]['materials'])
        self.assertIn(material, materials_in_section)

    def test_level_agnostic_materials_included_for_leveled_group(self):
        level_agnostic = Material.objects.create(subject=self.subject, title='Загальна тема', level=None)

        sections = get_materials_by_group([self.group.id])

        self.assertIn(level_agnostic, list(sections[0]['materials']))

    def test_empty_group_ids_return_no_sections(self):
        sections = get_materials_by_group([])
        self.assertEqual(sections, [])

    def test_group_without_level_only_matches_level_agnostic_materials(self):
        group_no_level = Group.objects.create(name='Group B', subject=self.subject)
        Material.objects.create(subject=self.subject, level=self.level, title='Тема з рівнем')
        level_agnostic = Material.objects.create(subject=self.subject, title='Без рівня', level=None)

        sections = get_materials_by_group([group_no_level.id])

        materials_in_section = list(sections[0]['materials'])
        self.assertEqual(materials_in_section, [level_agnostic])


class GetAllMaterialsGroupedTests(TestCase):
    def test_groups_materials_by_subject_and_level(self):
        subject = Subject.objects.create(name='Математика')
        level = Level.objects.create(subject=subject, name='Beginner')
        Material.objects.create(subject=subject, level=level, title='Тема 1')
        Material.objects.create(subject=subject, level=level, title='Тема 2')
        Material.objects.create(subject=subject, title='Без рівня')

        sections = get_all_materials_grouped()

        self.assertEqual(len(sections), 2)
        total_materials = sum(len(s['materials']) for s in sections)
        self.assertEqual(total_materials, 3)


class UserHasAccessToMaterialTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')
        self.level = Level.objects.create(subject=self.subject, name='Beginner')
        self.group = Group.objects.create(name='Group A', subject=self.subject, level=self.level)
        self.material = Material.objects.create(subject=self.subject, level=self.level, title='Тема 1')

    def test_superuser_always_has_access(self):
        admin = User.objects.create_user(username='admin1', password='pass12345', is_superuser=True)
        self.assertTrue(user_has_access_to_material(admin, self.material))

    def test_student_in_matching_group_has_access(self):
        user = User.objects.create_user(username='student1', password='pass12345')
        student = Student.objects.create(user=user)
        student.groups.add(self.group)

        self.assertTrue(user_has_access_to_material(user, self.material))

    def test_student_in_unrelated_group_has_no_access(self):
        other_subject = Subject.objects.create(name='Фізика')
        other_group = Group.objects.create(name='Group B', subject=other_subject)

        user = User.objects.create_user(username='student2', password='pass12345')
        student = Student.objects.create(user=user)
        student.groups.add(other_group)

        self.assertFalse(user_has_access_to_material(user, self.material))

    def test_teacher_in_matching_group_has_access(self):
        user = User.objects.create_user(username='teacher1', password='pass12345')
        teacher = Teacher.objects.create(user=user)
        self.group.teacher = teacher
        self.group.save()

        self.assertTrue(user_has_access_to_material(user, self.material))

    def test_user_without_role_has_no_access(self):
        user = User.objects.create_user(username='norole1', password='pass12345')
        self.assertFalse(user_has_access_to_material(user, self.material))

    def test_level_agnostic_material_accessible_to_leveled_group_student(self):
        level_agnostic_material = Material.objects.create(subject=self.subject, title='Без рівня')
        user = User.objects.create_user(username='student3', password='pass12345')
        student = Student.objects.create(user=user)
        student.groups.add(self.group)

        self.assertTrue(user_has_access_to_material(user, level_agnostic_material))
