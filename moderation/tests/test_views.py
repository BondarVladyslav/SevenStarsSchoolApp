from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from courses.models import Group, Level, Subject
from users.models import Parent, Student, Teacher

User = get_user_model()


class ModerationAccessControlTests(TestCase):

    def setUp(self):
        self.superuser = User.objects.create_user(
            username='admin1', password='pass12345', is_superuser=True, is_staff=True,
        )
        self.regular_user = User.objects.create_user(username='regular1', password='pass12345')

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('moderation_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_non_superuser_redirected_to_login(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse('moderation_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_superuser_can_access_dashboard(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('moderation_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'moderation/dashboard.html')


class ModerationDashboardViewTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='admin1', password='pass12345', is_superuser=True, is_staff=True,
        )
        self.client.force_login(self.superuser)

    def test_dashboard_lists_groups_students_teachers(self):
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject)

        teacher_user = User.objects.create_user(username='teacher1', password='pass12345')
        teacher = Teacher.objects.create(user=teacher_user)

        student_user = User.objects.create_user(username='student1', password='pass12345')
        student = Student.objects.create(user=student_user)

        response = self.client.get(reverse('moderation_dashboard'))

        self.assertIn(group, response.context['groups'])
        self.assertIn(teacher, response.context['teachers'])
        self.assertIn(student, response.context['students'])


class GroupCreateOrEditViewTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='admin1', password='pass12345', is_superuser=True, is_staff=True,
        )
        self.client.force_login(self.superuser)
        self.subject = Subject.objects.create(name='Математика')
        teacher_user = User.objects.create_user(username='teacher1', password='pass12345')
        self.teacher = Teacher.objects.create(user=teacher_user)

    def test_create_group(self):
        response = self.client.post(reverse('create_group'), {
            'action': 'change_group_name',
            'name': 'New Group',
            'teacher': self.teacher.id,
            'subject': self.subject.id,
        })

        self.assertRedirects(response, reverse('moderation_dashboard'))
        self.assertTrue(Group.objects.filter(name='New Group').exists())

    def test_edit_group(self):
        group = Group.objects.create(name='Old name', subject=self.subject)

        response = self.client.post(reverse('edit_group', args=[group.id]), {
            'action': 'change_group_name',
            'name': 'Updated name',
            'teacher': self.teacher.id,
            'subject': self.subject.id,
        })

        self.assertRedirects(response, reverse('moderation_dashboard'))
        group.refresh_from_db()
        self.assertEqual(group.name, 'Updated name')

    def test_delete_group(self):
        group = Group.objects.create(name='To delete', subject=self.subject)

        response = self.client.post(reverse('edit_group', args=[group.id]), {'action': 'delete_group'})

        self.assertRedirects(response, reverse('moderation_dashboard'))
        self.assertFalse(Group.objects.filter(id=group.id).exists())


class StudentEditOrCreateViewTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='admin1', password='pass12345', is_superuser=True, is_staff=True,
        )
        self.client.force_login(self.superuser)

    def test_create_student_generates_password_and_user(self):
        response = self.client.post(reverse('create_student'), {
            'action': 'change_student_info',
            'first_name': 'Іван',
            'last_name': 'Петров',
        })

        student = Student.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('edit_student', args=[student.id]))
        self.assertEqual(student.user.first_name, 'Іван')

        follow_up = self.client.get(reverse('edit_student', args=[student.id]))
        self.assertIsNotNone(follow_up.context['generated_password'])

    def test_edit_existing_student(self):
        user = User.objects.create_user(username='student1', password='pass12345')
        student = Student.objects.create(user=user)

        response = self.client.post(reverse('edit_student', args=[student.id]), {
            'action': 'change_student_info',
            'first_name': 'Оновлене',
            'last_name': 'Імʼя',
        })

        self.assertRedirects(response, reverse('moderation_dashboard'))
        user.refresh_from_db()
        self.assertEqual(user.first_name, 'Оновлене')

    def test_delete_student(self):
        user = User.objects.create_user(username='student2', password='pass12345')
        student = Student.objects.create(user=user)

        response = self.client.post(reverse('edit_student', args=[student.id]), {'action': 'delete_student'})

        self.assertRedirects(response, reverse('moderation_dashboard'))
        self.assertFalse(Student.objects.filter(id=student.id).exists())

    def test_reset_password_changes_hash(self):
        user = User.objects.create_user(username='student3', password='pass12345')
        student = Student.objects.create(user=user)
        old_hash = user.password

        response = self.client.post(reverse('edit_student', args=[student.id]), {'action': 'reset_password'})

        user.refresh_from_db()
        self.assertNotEqual(user.password, old_hash)
        self.assertIsNotNone(response.context['generated_password'])

    def test_add_and_remove_student_from_group(self):
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject)
        user = User.objects.create_user(username='student4', password='pass12345')
        student = Student.objects.create(user=user)

        self.client.post(reverse('edit_student', args=[student.id]), {
            'action': 'add_student_to_group', 'group_id': group.id,
        })
        self.assertTrue(student.groups.filter(pk=group.pk).exists())

        self.client.post(reverse('edit_student', args=[student.id]), {
            'action': 'remove_student_from_group', 'group_id': group.id,
        })
        self.assertFalse(student.groups.filter(pk=group.pk).exists())

    def test_add_and_remove_parent_from_student(self):
        student_user = User.objects.create_user(username='student5', password='pass12345')
        student = Student.objects.create(user=student_user)
        parent_user = User.objects.create_user(username='parent1', password='pass12345')
        parent = Parent.objects.create(user=parent_user)

        self.client.post(reverse('edit_student', args=[student.id]), {
            'action': 'add_parent_to_student', 'parent_id': parent.id,
        })
        self.assertTrue(student.parents.filter(pk=parent.pk).exists())

        self.client.post(reverse('edit_student', args=[student.id]), {
            'action': 'remove_parent_from_student', 'parent_id': parent.id,
        })
        self.assertFalse(student.parents.filter(pk=parent.pk).exists())

    def test_group_stats_not_shown_when_creating_new_student(self):
        response = self.client.get(reverse('create_student'))
        self.assertEqual(response.context['group_stats'], [])

    def test_group_stats_covers_all_groups_the_student_belongs_to(self):
        subject = Subject.objects.create(name='Математика')
        other_subject = Subject.objects.create(name='Англійська')
        teacher_user = User.objects.create_user(username='teacher10', password='pass12345')
        teacher = Teacher.objects.create(user=teacher_user)
        group = Group.objects.create(name='Group A', subject=subject, teacher=teacher)
        other_group = Group.objects.create(name='Group B', subject=other_subject, teacher=teacher)

        student_user = User.objects.create_user(username='student10', password='pass12345')
        student = Student.objects.create(user=student_user)
        student.groups.add(group, other_group)

        response = self.client.get(reverse('edit_student', args=[student.id]))

        group_ids = {s['group'].id for s in response.context['group_stats']}
        self.assertEqual(group_ids, {group.id, other_group.id})

    def test_group_stats_shows_lowercase_teacher_full_name(self):
        subject = Subject.objects.create(name='Математика')
        teacher_user = User.objects.create_user(
            username='teacher11', password='pass12345', first_name='Олена', last_name='Коваленко',
        )
        teacher = Teacher.objects.create(user=teacher_user)
        group = Group.objects.create(name='Group A', subject=subject, teacher=teacher)

        student_user = User.objects.create_user(username='student11', password='pass12345')
        student = Student.objects.create(user=student_user)
        student.groups.add(group)

        response = self.client.get(reverse('edit_student', args=[student.id]))

        content = response.content.decode()
        self.assertIn('олена коваленко', content)
        self.assertNotIn('Олена Коваленко', content)

    def test_group_stats_reflect_completion_and_grades(self):
        from datetime import timedelta

        from django.utils import timezone

        from courses.models import Homework, HomeworkSubmission

        subject = Subject.objects.create(name='Математика')
        teacher_user = User.objects.create_user(username='teacher12', password='pass12345')
        teacher = Teacher.objects.create(user=teacher_user)
        group = Group.objects.create(name='Group A', subject=subject, teacher=teacher)

        student_user = User.objects.create_user(username='student12', password='pass12345')
        student = Student.objects.create(user=student_user)
        student.groups.add(group)

        submitted_homework = Homework.objects.create(
            group=group, title='Здане', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
        )
        Homework.objects.create(
            group=group, title='Нездане', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
        )
        HomeworkSubmission.objects.create(
            homework=submitted_homework, student=student, status='checked', grade=35,
        )

        response = self.client.get(reverse('edit_student', args=[student.id]))

        stat = next(s for s in response.context['group_stats'] if s['group'].id == group.id)
        self.assertEqual(stat['completion_percentage'], 50)
        self.assertEqual(stat['average_homework_grade'], 35)


class ParentEditOrCreateViewTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='admin1', password='pass12345', is_superuser=True, is_staff=True,
        )
        self.client.force_login(self.superuser)

    def test_create_parent_links_to_student_via_query_param(self):
        student_user = User.objects.create_user(username='student1', password='pass12345')
        student = Student.objects.create(user=student_user)

        response = self.client.post(f"{reverse('create_parent')}?student_id={student.id}", {
            'action': 'change_parent_info',
            'first_name': 'Марія',
            'last_name': 'Іванова',
            'student_id': student.id,
        })

        parent = Parent.objects.get()
        self.assertIn(str(parent.id), response.url)
        self.assertTrue(parent.children.filter(pk=student.pk).exists())

    def test_delete_parent_redirects_to_student_when_provided(self):
        parent_user = User.objects.create_user(username='parent1', password='pass12345')
        parent = Parent.objects.create(user=parent_user)
        student_user = User.objects.create_user(username='student2', password='pass12345')
        student = Student.objects.create(user=student_user)

        response = self.client.post(
            f"{reverse('edit_parent', args=[parent.id])}?student_id={student.id}",
            {'action': 'delete_parent', 'student_id': student.id},
        )

        self.assertRedirects(response, reverse('edit_student', args=[student.id]))
        self.assertFalse(Parent.objects.filter(id=parent.id).exists())


class TeacherEditOrCreateViewTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='admin1', password='pass12345', is_superuser=True, is_staff=True,
        )
        self.client.force_login(self.superuser)

    def test_create_teacher(self):
        response = self.client.post(reverse('create_teacher'), {
            'action': 'change_teacher_info',
            'first_name': 'Петро',
            'last_name': 'Сидоренко',
            'groups': [],
        })

        teacher = Teacher.objects.get()
        self.assertRedirects(response, reverse('edit_teacher', args=[teacher.id]))

    def test_delete_teacher(self):
        user = User.objects.create_user(username='teacher1', password='pass12345')
        teacher = Teacher.objects.create(user=user)

        response = self.client.post(reverse('edit_teacher', args=[teacher.id]), {'action': 'delete_teacher'})

        self.assertRedirects(response, reverse('moderation_dashboard'))
        self.assertFalse(Teacher.objects.filter(id=teacher.id).exists())

    def test_add_and_remove_group_from_teacher(self):
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject)
        user = User.objects.create_user(username='teacher2', password='pass12345')
        teacher = Teacher.objects.create(user=user)

        self.client.post(reverse('edit_teacher', args=[teacher.id]), {
            'action': 'change_teacher_info',
            'first_name': 'Петро',
            'last_name': 'Іванов',
            'group_ids': [group.id],
        })
        group.refresh_from_db()
        self.assertEqual(group.teacher, teacher)

        self.client.post(reverse('edit_teacher', args=[teacher.id]), {
            'action': 'change_teacher_info',
            'first_name': 'Петро',
            'last_name': 'Іванов',
            'group_ids': [],
        })
        group.refresh_from_db()
        self.assertIsNone(group.teacher)

    def test_cannot_reassign_group_that_already_has_teacher(self):
        subject = Subject.objects.create(name='Математика')
        other_user = User.objects.create_user(username='teacher3', password='pass12345')
        other_teacher = Teacher.objects.create(user=other_user)
        group = Group.objects.create(name='Group B', subject=subject, teacher=other_teacher)

        user = User.objects.create_user(username='teacher4', password='pass12345')
        teacher = Teacher.objects.create(user=user)

        self.client.post(reverse('edit_teacher', args=[teacher.id]), {
            'action': 'change_teacher_info',
            'first_name': 'Іван',
            'last_name': 'Петренко',
            'group_ids': [group.id],
        })

        group.refresh_from_db()
        self.assertEqual(group.teacher, other_teacher)

    def test_saving_name_without_group_ids_does_not_wipe_existing_groups(self):
        subject = Subject.objects.create(name='Математика')
        user = User.objects.create_user(username='teacher5', password='pass12345')
        teacher = Teacher.objects.create(user=user)
        group = Group.objects.create(name='Group C', subject=subject, teacher=teacher)

        response = self.client.post(reverse('edit_teacher', args=[teacher.id]), {
            'action': 'change_teacher_info',
            'first_name': 'Оновлене',
            'last_name': 'Ім’я',
            'group_ids': [group.id],
        })

        self.assertRedirects(response, reverse('moderation_dashboard'))
        group.refresh_from_db()
        self.assertEqual(group.teacher, teacher)


class SubjectAndLevelViewTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='admin1', password='pass12345', is_superuser=True, is_staff=True,
        )
        self.client.force_login(self.superuser)

    def test_create_subject(self):
        response = self.client.post(reverse('create_subject'), {'action': 'save', 'name': 'Хімія'})
        self.assertRedirects(response, reverse('moderation_dashboard'))
        self.assertTrue(Subject.objects.filter(name='Хімія').exists())

    def test_delete_subject(self):
        subject = Subject.objects.create(name='Біологія')
        response = self.client.post(reverse('edit_subject', args=[subject.id]), {'action': 'delete_subject'})
        self.assertRedirects(response, reverse('moderation_dashboard'))
        self.assertFalse(Subject.objects.filter(id=subject.id).exists())

    def test_create_level(self):
        subject = Subject.objects.create(name='Математика')
        response = self.client.post(reverse('create_level'), {
            'action': 'save', 'subject': subject.id, 'name': 'Advanced', 'order': 1,
        })
        level = Level.objects.get()
        self.assertRedirects(response, reverse('edit_subject', args=[subject.id]))
        self.assertEqual(level.name, 'Advanced')

    def test_delete_level_redirects_to_subject(self):
        subject = Subject.objects.create(name='Математика')
        level = Level.objects.create(subject=subject, name='Beginner')

        response = self.client.post(reverse('edit_level', args=[level.id]), {'action': 'delete_level'})

        self.assertRedirects(response, reverse('edit_subject', args=[subject.id]))
        self.assertFalse(Level.objects.filter(id=level.id).exists())


class ManageGroupScheduleViewTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='admin1', password='pass12345', is_superuser=True, is_staff=True,
        )
        self.client.force_login(self.superuser)
        subject = Subject.objects.create(name='Математика')
        self.group = Group.objects.create(name='Group A', subject=subject)

    def test_add_lesson(self):
        response = self.client.post(reverse('manage_group_schedule', args=[self.group.id]), {
            'action': 'add_lesson',
            'weekday': 0,
            'start_time': '10:00',
            'end_time': '11:00',
        })

        self.assertRedirects(response, reverse('manage_group_schedule', args=[self.group.id]))
        self.assertEqual(self.group.lessons.count(), 1)

    def test_delete_lesson(self):
        from schedule.models import Lesson

        lesson = Lesson.objects.create(group=self.group, weekday=0, start_time='10:00', end_time='11:00')

        response = self.client.post(reverse('manage_group_schedule', args=[self.group.id]), {
            'action': 'delete_lesson',
            'lesson_id': lesson.id,
        })

        self.assertRedirects(response, reverse('manage_group_schedule', args=[self.group.id]))
        self.assertFalse(Lesson.objects.filter(id=lesson.id).exists())


class ScheduleExceptionsViewTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='admin1', password='pass12345', is_superuser=True, is_staff=True,
        )
        self.client.force_login(self.superuser)
        subject = Subject.objects.create(name='Математика')
        self.group = Group.objects.create(name='Group A', subject=subject)

        from datetime import time
        from schedule.models import Lesson

        self.lesson = Lesson.objects.create(
            group=self.group, weekday=0, start_time=time(10, 0), end_time=time(11, 0),
        )

    def test_add_cancelled_exception(self):
        from django.utils import timezone

        today = timezone.localdate()
        monday = today - timezone.timedelta(days=today.weekday())

        response = self.client.post(reverse('manage_schedule_exceptions', args=[self.group.id]), {
            'action': 'add_exception',
            'lesson_occurrence': f'{self.lesson.id}_{monday.isoformat()}',
            'exception_type': 'cancelled',
        })

        self.assertRedirects(response, reverse('manage_schedule_exceptions', args=[self.group.id]))

        from schedule.models import ScheduleException
        self.assertTrue(
            ScheduleException.objects.filter(lesson=self.lesson, original_date=monday).exists()
        )

    def test_add_exception_without_data_is_bad_request(self):
        response = self.client.post(reverse('manage_schedule_exceptions', args=[self.group.id]), {
            'action': 'add_exception',
        })
        self.assertEqual(response.status_code, 400)

    def test_rescheduled_exception_without_new_date_is_rejected(self):
        from django.utils import timezone

        today = timezone.localdate()
        monday = today - timezone.timedelta(days=today.weekday())

        response = self.client.post(reverse('manage_schedule_exceptions', args=[self.group.id]), {
            'action': 'add_exception',
            'lesson_occurrence': f'{self.lesson.id}_{monday.isoformat()}',
            'exception_type': 'rescheduled',
        })

        self.assertEqual(response.status_code, 400)

class ManageStudentAbsencesViewTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_user(
            username='admin1', password='pass12345', is_superuser=True, is_staff=True,
        )
        self.client.force_login(self.superuser)

        from datetime import time
        from schedule.models import Lesson

        subject = Subject.objects.create(name='Математика')
        self.teacher_user = User.objects.create_user(username='teacher1', password='pass12345')
        self.teacher = Teacher.objects.create(user=self.teacher_user)
        self.group = Group.objects.create(name='Group A', subject=subject, teacher=self.teacher)
        self.lesson = Lesson.objects.create(
            group=self.group, weekday=0, start_time=time(10, 0), end_time=time(11, 0),
        )

        student_user = User.objects.create_user(username='student1', password='pass12345')
        self.student = Student.objects.create(user=student_user)
        self.student.groups.add(self.group)

        self.missed_date = timezone.now().date() + timedelta(days=7)
        while self.missed_date.weekday() != 0:
            self.missed_date += timedelta(days=1)

    def test_non_superuser_gets_redirected(self):
        regular_user = User.objects.create_user(username='regular1', password='pass12345')
        self.client.force_login(regular_user)

        response = self.client.get(reverse('manage_student_absences', args=[self.student.id]))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_add_absence_with_makeup_lesson_syncs_is_absent(self):
        from datetime import time

        from schedule.models import Lesson, LessonAbsence, LessonParticipation

        other_subject = Subject.objects.create(name='Англійська')
        other_teacher_user = User.objects.create_user(username='teacher2', password='pass12345')
        other_teacher = Teacher.objects.create(user=other_teacher_user)
        other_group = Group.objects.create(name='Group B', subject=other_subject, teacher=other_teacher)
        makeup_date = self.missed_date + timedelta(days=1)
        other_lesson = Lesson.objects.create(
            group=other_group, weekday=makeup_date.weekday(), start_time=time(12, 0), end_time=time(13, 0),
        )

        response = self.client.post(
            reverse('manage_student_absences', args=[self.student.id]),
            {
                'action': 'add_absence',
                'lesson_occurrence': f'{self.lesson.id}_{self.missed_date.isoformat()}',
                'makeup_choice': 'lesson',
                'makeup_occurrence': f'{other_lesson.id}_{makeup_date.isoformat()}',
            },
        )

        self.assertRedirects(response, reverse('manage_student_absences', args=[self.student.id]))
        absence = LessonAbsence.objects.get(student=self.student, lesson=self.lesson)
        self.assertEqual(absence.makeup_lesson, other_lesson)
        self.assertEqual(absence.makeup_date, makeup_date)

        participation = LessonParticipation.objects.get(
            lesson=self.lesson, lesson_date=self.missed_date, student=self.student,
        )
        self.assertTrue(participation.is_absent)
        self.assertIsNone(participation.score)

    def test_add_absence_with_custom_makeup_time(self):
        from schedule.models import LessonAbsence

        makeup_date = self.missed_date + timedelta(days=2)

        response = self.client.post(
            reverse('manage_student_absences', args=[self.student.id]),
            {
                'action': 'add_absence',
                'lesson_occurrence': f'{self.lesson.id}_{self.missed_date.isoformat()}',
                'makeup_choice': 'custom',
                'makeup_date': makeup_date.isoformat(),
                'makeup_start_time': '15:00',
                'makeup_end_time': '16:00',
            },
        )

        self.assertRedirects(response, reverse('manage_student_absences', args=[self.student.id]))
        absence = LessonAbsence.objects.get(student=self.student, lesson=self.lesson)
        self.assertIsNone(absence.makeup_lesson)
        self.assertEqual(absence.makeup_date, makeup_date)

    def test_delete_absence_reverts_is_absent(self):
        from schedule.models import LessonAbsence, LessonParticipation

        absence = LessonAbsence.objects.create(
            student=self.student, lesson=self.lesson, missed_date=self.missed_date,
        )
        LessonParticipation.objects.create(
            lesson=self.lesson, lesson_date=self.missed_date, student=self.student, is_absent=True,
        )

        response = self.client.post(
            reverse('manage_student_absences', args=[self.student.id]),
            {'action': 'delete_absence', 'absence_id': absence.id},
        )

        self.assertRedirects(response, reverse('manage_student_absences', args=[self.student.id]))
        self.assertFalse(LessonAbsence.objects.filter(id=absence.id).exists())
        participation = LessonParticipation.objects.get(
            lesson=self.lesson, lesson_date=self.missed_date, student=self.student,
        )
        self.assertFalse(participation.is_absent)

    def test_cannot_add_absence_for_lesson_outside_students_groups(self):
        from datetime import time

        from schedule.models import Lesson

        other_subject = Subject.objects.create(name='Англійська')
        other_group = Group.objects.create(name='Group B', subject=other_subject)
        foreign_lesson = Lesson.objects.create(
            group=other_group, weekday=self.missed_date.weekday(), start_time=time(9, 0), end_time=time(10, 0),
        )

        response = self.client.post(
            reverse('manage_student_absences', args=[self.student.id]),
            {
                'action': 'add_absence',
                'lesson_occurrence': f'{foreign_lesson.id}_{self.missed_date.isoformat()}',
            },
        )

        self.assertEqual(response.status_code, 404)