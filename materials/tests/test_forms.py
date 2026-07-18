from django.test import TestCase

from materials.forms import MaterialEditForm


class MaterialEditFormTests(TestCase):
    def test_valid_with_title(self):
        form = MaterialEditForm(data={'title': 'Нова тема', 'description': 'Опис'})
        self.assertTrue(form.is_valid())

    def test_description_is_optional(self):
        form = MaterialEditForm(data={'title': 'Нова тема', 'description': ''})
        self.assertTrue(form.is_valid())

    def test_title_is_required(self):
        form = MaterialEditForm(data={'title': '', 'description': 'Опис'})
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
