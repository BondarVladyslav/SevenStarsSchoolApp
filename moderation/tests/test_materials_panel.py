import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from courses.models import Group, Level, Subject
from materials.models import Material, MaterialFile
from schedule.models import Lesson, ScheduleException
from users.models import Parent, Student, Teacher

User = get_user_model()


class SuperuserTestCase(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='admin1', password='pass12345', is_superuser=True, is_staff=True,
        )
        self.client.force_login(self.superuser)


class GroupCreateOrEditGetPageTests(SuperuserTestCase):
    def test_get_create_page_renders_with_levels(self):
        subject = Subject.objects.create(name='Математика')
        level = Level.objects.create(subject=subject, name='Beginner')

        response = self.client.get(reverse('create_group'))

        self.assertEqual(response.status_code, 200)
        self.assertIn(level, response.context['levels'])
        self.assertContains(response, 'Beginner')

    def test_get_edit_page_for_existing_group(self):
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject)

        response = self.client.get(reverse('edit_group', args=[group.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['group'], group)


class ParentEditOrCreateFullFlowTests(SuperuserTestCase):
    def setUp(self):
        super().setUp()
        user = User.objects.create_user(username='parent1', password='pass12345')
        self.parent = Parent.objects.create(user=user)

    def test_reset_password_changes_hash(self):
        old_hash = self.parent.user.password

        response = self.client.post(reverse('edit_parent', args=[self.parent.id]), {
            'action': 'reset_password',
        })

        self.parent.user.refresh_from_db()
        self.assertNotEqual(self.parent.user.password, old_hash)
        self.assertIsNotNone(response.context['generated_password'])

    def test_editing_existing_parent_updates_name_and_redirects_to_dashboard(self):
        response = self.client.post(reverse('edit_parent', args=[self.parent.id]), {
            'action': 'change_parent_info',
            'first_name': 'Оновлене',
            'last_name': "Ім'я",
        })

        self.assertRedirects(response, reverse('moderation_dashboard'))
        self.parent.user.refresh_from_db()
        self.assertEqual(self.parent.user.first_name, 'Оновлене')

    def test_editing_existing_parent_with_student_id_redirects_to_student(self):
        student_user = User.objects.create_user(username='student1', password='pass12345')
        student = Student.objects.create(user=student_user)

        response = self.client.post(
            f"{reverse('edit_parent', args=[self.parent.id])}?student_id={student.id}",
            {
                'action': 'change_parent_info',
                'first_name': 'Оновлене',
                'last_name': "Ім'я",
                'student_id': student.id,
            },
        )

        self.assertRedirects(response, reverse('edit_student', args=[student.id]))

    def test_add_and_remove_child_from_parent(self):
        student_user = User.objects.create_user(username='student2', password='pass12345')
        student = Student.objects.create(user=student_user)

        response = self.client.post(reverse('edit_parent', args=[self.parent.id]), {
            'action': 'add_child_to_parent', 'child_id': student.id,
        })
        self.assertRedirects(response, reverse('edit_parent', args=[self.parent.id]))
        self.assertTrue(self.parent.children.filter(pk=student.pk).exists())

        response = self.client.post(reverse('edit_parent', args=[self.parent.id]), {
            'action': 'remove_child_from_parent', 'child_id': student.id,
        })
        self.assertRedirects(response, reverse('edit_parent', args=[self.parent.id]))
        self.assertFalse(self.parent.children.filter(pk=student.pk).exists())

    def test_delete_parent_without_student_context_redirects_to_dashboard(self):
        response = self.client.post(reverse('edit_parent', args=[self.parent.id]), {
            'action': 'delete_parent',
        })

        self.assertRedirects(response, reverse('moderation_dashboard'))
        self.assertFalse(Parent.objects.filter(id=self.parent.id).exists())

    def test_generated_password_shown_once_after_parent_creation(self):
        response = self.client.post(reverse('create_parent'), {
            'action': 'change_parent_info',
            'first_name': 'Нова',
            'last_name': 'Особа',
        })

        new_parent = Parent.objects.exclude(id=self.parent.id).get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('edit_parent', args=[new_parent.id]))

        follow_up = self.client.get(reverse('edit_parent', args=[new_parent.id]))
        self.assertIsNotNone(follow_up.context['generated_password'])

        second_visit = self.client.get(reverse('edit_parent', args=[new_parent.id]))
        self.assertIsNone(second_visit.context['generated_password'])


class TeacherEditOrCreateFullFlowTests(SuperuserTestCase):
    def setUp(self):
        super().setUp()
        user = User.objects.create_user(username='teacher1', password='pass12345')
        self.teacher = Teacher.objects.create(user=user)

    def test_reset_password_changes_hash(self):
        old_hash = self.teacher.user.password

        response = self.client.post(reverse('edit_teacher', args=[self.teacher.id]), {
            'action': 'reset_password',
        })

        self.teacher.user.refresh_from_db()
        self.assertNotEqual(self.teacher.user.password, old_hash)
        self.assertIsNotNone(response.context['generated_password'])

    def test_editing_existing_teacher_updates_name_and_redirects_to_dashboard(self):
        response = self.client.post(reverse('edit_teacher', args=[self.teacher.id]), {
            'action': 'change_teacher_info',
            'first_name': 'Оновлене',
            'last_name': "Ім'я",
            'groups': [],
        })

        self.assertRedirects(response, reverse('moderation_dashboard'))
        self.teacher.user.refresh_from_db()
        self.assertEqual(self.teacher.user.first_name, 'Оновлене')


class SubjectEditOrCreateGetPageTests(SuperuserTestCase):
    def test_get_edit_page_lists_levels_of_subject(self):
        subject = Subject.objects.create(name='Математика')
        level = Level.objects.create(subject=subject, name='Beginner')

        response = self.client.get(reverse('edit_subject', args=[subject.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIn(level, response.context['levels'])

    def test_get_create_page_has_no_levels(self):
        response = self.client.get(reverse('create_subject'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['levels']), [])


class LevelEditOrCreateGetPageTests(SuperuserTestCase):
    def test_create_level_page_prefills_subject_from_query_param(self):
        subject = Subject.objects.create(name='Математика')

        response = self.client.get(f"{reverse('create_level')}?subject_id={subject.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.context['form'].initial['subject']), str(subject.id))

    def test_delete_level_action_with_no_existing_level_redirects_to_dashboard(self):
        response = self.client.post(reverse('create_level'), {'action': 'delete_level'})
        self.assertRedirects(response, reverse('moderation_dashboard'))


class ManageScheduleExceptionsDeleteTests(SuperuserTestCase):
    def setUp(self):
        super().setUp()
        from datetime import time

        subject = Subject.objects.create(name='Математика')
        self.group = Group.objects.create(name='Group A', subject=subject)
        self.lesson = Lesson.objects.create(
            group=self.group, weekday=0, start_time=time(10, 0), end_time=time(11, 0),
        )

    def test_delete_exception(self):
        from datetime import date

        exception = ScheduleException.objects.create(
            lesson=self.lesson, original_date=date(2026, 7, 13), exception_type='cancelled',
        )

        response = self.client.post(reverse('manage_schedule_exceptions', args=[self.group.id]), {
            'action': 'delete_exception',
            'exception_id': exception.id,
        })

        self.assertRedirects(response, reverse('manage_schedule_exceptions', args=[self.group.id]))
        self.assertFalse(ScheduleException.objects.filter(id=exception.id).exists())


_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='ssschool_test_media_moderation_')


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class ModerationMaterialsPanelTests(SuperuserTestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.subject = Subject.objects.create(name='Математика')
        self.level = Level.objects.create(subject=self.subject, name='Beginner')

    def test_get_create_material_page(self):
        response = self.client.get(reverse('create_material'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_edit'])

        content = response.content.decode()
        self.assertIn('id="materialForm"', content)
        self.assertIn('id="subjectFieldError"', content)
        self.assertIn('id="subjectSearchSelect"', content)
        self.assertIn('id="levelSearchSelect"', content)

    def test_get_edit_material_page(self):
        material = Material.objects.create(subject=self.subject, title='Тема 1')

        response = self.client.get(reverse('edit_material', args=[material.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_edit'])

    def test_create_material_with_level(self):
        response = self.client.post(reverse('create_material'), {
            'action': 'save',
            'title': 'Нова тема',
            'description': 'Опис',
            'level_id': self.level.id,
        })

        self.assertRedirects(response, reverse('materials_list'))
        material = Material.objects.get(title='Нова тема')
        self.assertEqual(material.level, self.level)
        self.assertEqual(material.subject, self.subject)

    def test_create_material_with_subject_only(self):
        response = self.client.post(reverse('create_material'), {
            'action': 'save',
            'title': 'Тема без рівня',
            'description': 'Опис',
            'subject_id': self.subject.id,
        })

        self.assertRedirects(response, reverse('materials_list'))
        material = Material.objects.get(title='Тема без рівня')
        self.assertIsNone(material.level)

    def test_create_material_without_subject_or_level_is_bad_request(self):
        response = self.client.post(reverse('create_material'), {
            'action': 'save',
            'title': 'Тема',
            'description': 'Опис',
        })

        self.assertEqual(response.status_code, 400)

    def test_create_material_with_too_many_files_is_bad_request(self):
        from django.core.files.storage import default_storage

        keys = []
        for i in range(8):
            key = f'materials/f{i}.txt'
            default_storage.save(key, SimpleUploadedFile(f'f{i}.txt', b'content'))
            keys.append(key)

        response = self.client.post(reverse('create_material'), {
            'action': 'save',
            'title': 'Тема',
            'description': 'Опис',
            'subject_id': self.subject.id,
            'uploaded_keys': keys,
        })

        self.assertEqual(response.status_code, 400)

    def test_create_material_with_nonexistent_key_is_bad_request(self):
        response = self.client.post(reverse('create_material'), {
            'action': 'save',
            'title': 'Тема',
            'description': 'Опис',
            'subject_id': self.subject.id,
            'uploaded_keys': ['materials/does-not-exist.txt'],
        })

        self.assertEqual(response.status_code, 400)

    def test_edit_material_switching_from_level_to_subject_only(self):
        material = Material.objects.create(subject=self.subject, level=self.level, title='Тема')

        response = self.client.post(reverse('edit_material', args=[material.id]), {
            'action': 'save',
            'title': 'Тема',
            'description': 'Опис',
            'subject_id': self.subject.id,
        })

        self.assertRedirects(response, reverse('materials_list'))
        material.refresh_from_db()
        self.assertIsNone(material.level)

    def test_delete_material_file(self):
        material = Material.objects.create(subject=self.subject, title='Тема')
        material_file = MaterialFile.objects.create(
            material=material, file=SimpleUploadedFile('a.txt', b'content'),
        )

        response = self.client.post(reverse('edit_material', args=[material.id]), {
            'action': 'delete_file',
            'file_id': material_file.id,
        })

        self.assertRedirects(response, reverse('edit_material', args=[material.id]))
        self.assertFalse(MaterialFile.objects.filter(id=material_file.id).exists())

    def test_create_material_with_files_uploads_them(self):
        from django.core.files.storage import default_storage

        key_a = 'materials/a.txt'
        key_b = 'materials/b.txt'
        default_storage.save(key_a, SimpleUploadedFile('a.txt', b'one'))
        default_storage.save(key_b, SimpleUploadedFile('b.txt', b'two'))

        response = self.client.post(reverse('create_material'), {
            'action': 'save',
            'title': 'Тема з файлами',
            'description': 'Опис',
            'subject_id': self.subject.id,
            'uploaded_keys': [key_a, key_b],
        })

        self.assertRedirects(response, reverse('materials_list'))
        material = Material.objects.get(title='Тема з файлами')
        self.assertEqual(material.files.count(), 2)

    def test_delete_material_removes_its_files(self):
        material = Material.objects.create(subject=self.subject, title='Тема')
        material_file = MaterialFile.objects.create(
            material=material, file=SimpleUploadedFile('a.txt', b'content'),
        )

        response = self.client.post(reverse('edit_material', args=[material.id]), {
            'action': 'delete_material',
        })

        self.assertRedirects(response, reverse('materials_list'))
        self.assertFalse(Material.objects.filter(id=material.id).exists())
        self.assertFalse(MaterialFile.objects.filter(id=material_file.id).exists())


class MaterialUploadUrlViewTests(SuperuserTestCase):
    def test_non_superuser_redirected_to_login(self):
        user = User.objects.create_user(username='norole1', password='pass12345')
        self.client.force_login(user)

        response = self.client.post(
            reverse('material_upload_url'),
            data='{"filenames": ["a.txt"]}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_get_request_is_bad_request(self):
        response = self.client.get(reverse('material_upload_url'))
        self.assertEqual(response.status_code, 400)

    def test_invalid_json_body_is_bad_request(self):
        response = self.client.post(
            reverse('material_upload_url'),
            data='not json',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_empty_filenames_is_bad_request(self):
        response = self.client.post(
            reverse('material_upload_url'),
            data='{"filenames": []}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_too_many_filenames_is_bad_request(self):
        response = self.client.post(
            reverse('material_upload_url'),
            data='{"filenames": ["a.txt", "b.txt", "c.txt", "d.txt", "e.txt", "f.txt", "g.txt", "h.txt"]}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_non_s3_storage_is_bad_request(self):
        response = self.client.post(
            reverse('material_upload_url'),
            data='{"filenames": ["a.txt"]}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)