from django.test import TestCase

from courses.forms import CheckSubmissionForm, HomeworkPostForm, HomeworkSubmissionForm


class HomeworkPostFormTests(TestCase):
    def test_deadline_field_uses_datetime_local_widget(self):
        form = HomeworkPostForm()
        self.assertEqual(form.fields['deadline'].widget.input_type, 'datetime-local')

    def test_deadline_field_is_required(self):
        form = HomeworkPostForm(data={'title': 'Тест', 'description': 'Опис', 'deadline': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('deadline', form.errors)

    def test_valid_data_creates_valid_form(self):
        form = HomeworkPostForm(data={
            'title': 'Тест',
            'description': 'Опис',
            'deadline': '2026-08-01T10:00',
        })
        self.assertTrue(form.is_valid())

    def test_missing_title_is_invalid(self):
        form = HomeworkPostForm(data={
            'title': '',
            'description': 'Опис',
            'deadline': '2026-08-01T10:00',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)


class HomeworkSubmissionFormTests(TestCase):
    def test_only_text_field_present(self):
        form = HomeworkSubmissionForm()
        self.assertEqual(list(form.fields.keys()), ['text'])

    def test_form_valid_with_text(self):
        form = HomeworkSubmissionForm(data={'text': 'Моя відповідь'})
        self.assertTrue(form.is_valid())

    def test_form_valid_with_blank_text(self):
        form = HomeworkSubmissionForm(data={'text': ''})
        self.assertTrue(form.is_valid())


class CheckSubmissionFormTests(TestCase):
    def test_grade_within_range_is_valid(self):
        form = CheckSubmissionForm(data={'grade': 42, 'status': 'checked', 'teacher_comment': 'Добре'})
        self.assertTrue(form.is_valid())

    def test_grade_above_max_is_invalid(self):
        form = CheckSubmissionForm(data={'grade': 51, 'status': 'checked', 'teacher_comment': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('grade', form.errors)

    def test_grade_below_min_is_invalid(self):
        form = CheckSubmissionForm(data={'grade': -1, 'status': 'checked', 'teacher_comment': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('grade', form.errors)

    def test_grade_is_optional(self):
        form = CheckSubmissionForm(data={'status': 'pending', 'teacher_comment': ''})
        self.assertTrue(form.is_valid())
