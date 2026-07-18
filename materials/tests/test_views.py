import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from courses.models import Group, Level, Subject
from materials.models import Material, MaterialFile
from users.models import Student, Teacher

User = get_user_model()


def make_user_with_role(username, role_model, **user_kwargs):
    user = User.objects.create_user(username=username, password='pass12345', **user_kwargs)
    role = role_model.objects.create(user=user)
    return user, role


class MaterialsViewTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')
        self.level = Level.objects.create(subject=self.subject, name='Beginner')
        self.group = Group.objects.create(name='Group A', subject=self.subject, level=self.level)
        Material.objects.create(subject=self.subject, level=self.level, title='Тема 1')

    def test_superuser_sees_all_materials(self):
        admin = User.objects.create_user(username='admin1', password='pass12345', is_superuser=True)
        self.client.force_login(admin)

        response = self.client.get(reverse('materials_list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'materials/materials_list.html')

    def test_teacher_sees_materials_for_their_groups(self):
        user, teacher = make_user_with_role('teacher1', Teacher)
        self.group.teacher = teacher
        self.group.save()

        self.client.force_login(user)
        response = self.client.get(reverse('materials_list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'materials/materials_list.html')

    def test_superuser_sees_edit_and_delete_buttons(self):
        admin = User.objects.create_user(username='admin1', password='pass12345', is_superuser=True)
        material = Material.objects.get()
        self.client.force_login(admin)

        response = self.client.get(reverse('materials_list'))

        self.assertContains(response, reverse('edit_material', args=[material.id]))
        self.assertContains(response, 'name="action" value="delete_material"')

    def test_teacher_does_not_see_edit_and_delete_buttons(self):
        user, teacher = make_user_with_role('teacher1', Teacher)
        self.group.teacher = teacher
        self.group.save()
        material = Material.objects.get()

        self.client.force_login(user)
        response = self.client.get(reverse('materials_list'))

        self.assertNotContains(response, reverse('edit_material', args=[material.id]))
        self.assertNotContains(response, 'name="action" value="delete_material"')

    def test_superuser_can_delete_material_from_the_list_page(self):
        admin = User.objects.create_user(username='admin1', password='pass12345', is_superuser=True)
        material = Material.objects.get()
        self.client.force_login(admin)

        response = self.client.post(reverse('edit_material', args=[material.id]), {
            'action': 'delete_material',
        })

        self.assertRedirects(response, reverse('materials_list'))
        self.assertFalse(Material.objects.filter(id=material.id).exists())

    def test_user_without_role_gets_permission_denied(self):
        user = User.objects.create_user(username='norole1', password='pass12345')
        self.client.force_login(user)

        response = self.client.get(reverse('materials_list'))

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('materials_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_student_in_group_sees_materials(self):
        user, student = make_user_with_role('student1', Student)
        student.groups.add(self.group)
        self.client.force_login(user)

        response = self.client.get(reverse('materials_list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'materials/materials_list.html')

    def test_student_not_in_any_group_sees_empty_materials_list(self):
        user, _student = make_user_with_role('student2', Student)
        self.client.force_login(user)

        response = self.client.get(reverse('materials_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['sections'], [])


class MaterialDetailViewTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')
        self.level = Level.objects.create(subject=self.subject, name='Beginner')
        self.group = Group.objects.create(name='Group A', subject=self.subject, level=self.level)
        self.material = Material.objects.create(subject=self.subject, level=self.level, title='Тема 1')

    def test_student_with_access_can_view(self):
        user, student = make_user_with_role('student1', Student)
        student.groups.add(self.group)

        self.client.force_login(user)
        response = self.client.get(reverse('material_detail', args=[self.material.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['material'], self.material)

    def test_student_without_access_gets_permission_denied(self):
        user, _student = make_user_with_role('student2', Student)

        self.client.force_login(user)
        response = self.client.get(reverse('material_detail', args=[self.material.id]))

        self.assertEqual(response.status_code, 403)

    def test_nonexistent_material_returns_404(self):
        admin = User.objects.create_user(username='admin1', password='pass12345', is_superuser=True)
        self.client.force_login(admin)

        response = self.client.get(reverse('material_detail', args=[99999]))

        self.assertEqual(response.status_code, 404)


_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='ssschool_test_media_materials_')


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class DownloadMaterialFileViewTests(TestCase):
    """Uses an isolated temp MEDIA_ROOT instead of the real media/ folder, and
    removes it wholesale in tearDownClass. This avoids Windows' PermissionError
    when trying to delete a file that FileResponse just streamed and the OS
    hasn't fully released the handle for yet."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')
        self.level = Level.objects.create(subject=self.subject, name='Beginner')
        self.group = Group.objects.create(name='Group A', subject=self.subject, level=self.level)
        self.material = Material.objects.create(subject=self.subject, level=self.level, title='Тема 1')
        self.material_file = MaterialFile.objects.create(
            material=self.material,
            file=SimpleUploadedFile('lesson.pdf', b'material content'),
        )

    def test_student_with_access_can_download(self):
        user, student = make_user_with_role('student1', Student)
        student.groups.add(self.group)

        self.client.force_login(user)
        response = self.client.get(reverse('download_material_file', args=[self.material_file.id]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.material_file.file.url)

    def test_student_without_access_gets_permission_denied(self):
        user, _student = make_user_with_role('student2', Student)

        self.client.force_login(user)
        response = self.client.get(reverse('download_material_file', args=[self.material_file.id]))

        self.assertEqual(response.status_code, 403)

    def test_missing_file_on_disk_returns_404(self):
        admin = User.objects.create_user(username='admin1', password='pass12345', is_superuser=True)
        self.material_file.file.delete(save=False)
        self.client.force_login(admin)

        response = self.client.get(reverse('download_material_file', args=[self.material_file.id]))

        self.assertEqual(response.status_code, 404)