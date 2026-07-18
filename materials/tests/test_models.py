from django.test import TestCase

from courses.models import Level, Subject
from materials.models import Material, MaterialFile


class MaterialModelTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')

    def test_str_representation(self):
        material = Material.objects.create(subject=self.subject, title='Тема 1')
        self.assertEqual(str(material), 'Тема 1')

    def test_material_can_have_level(self):
        level = Level.objects.create(subject=self.subject, name='Beginner')
        material = Material.objects.create(subject=self.subject, level=level, title='Тема 1')
        self.assertEqual(material.level, level)

    def test_material_level_is_optional(self):
        material = Material.objects.create(subject=self.subject, title='Тема без рівня')
        self.assertIsNone(material.level)

    def test_material_deleted_when_subject_deleted(self):
        material = Material.objects.create(subject=self.subject, title='Тема 1')
        material_id = material.id

        self.subject.delete()

        self.assertFalse(Material.objects.filter(id=material_id).exists())

    def test_material_deleted_when_level_deleted(self):
        level = Level.objects.create(subject=self.subject, name='Beginner')
        material = Material.objects.create(subject=self.subject, level=level, title='Тема 1')
        material_id = material.id

        level.delete()

        self.assertFalse(Material.objects.filter(id=material_id).exists())


class MaterialFileModelTests(TestCase):
    def test_material_file_deleted_when_material_deleted(self):
        subject = Subject.objects.create(name='Математика')
        material = Material.objects.create(subject=subject, title='Тема 1')
        material_file = MaterialFile.objects.create(material=material, file='materials/test.txt')
        file_id = material_file.id

        material.delete()

        self.assertFalse(MaterialFile.objects.filter(id=file_id).exists())
