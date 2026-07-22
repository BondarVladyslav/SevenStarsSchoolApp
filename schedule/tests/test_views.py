from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from courses.models import Group, Subject
from schedule.models import Lesson, LessonParticipation
from users.models import Parent, Student, Teacher

User = get_user_model()


def make_user_with_role(username, role_model, **user_kwargs):
    user = User.objects.create_user(username=username, password='pass12345', **user_kwargs)
    role = role_model.objects.create(user=user)
    return user, role


class ScheduleViewTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')
        self.group = Group.objects.create(name='Group A', subject=self.subject)

    def test_student_sees_own_schedule(self):
        user, student = make_user_with_role('student1', Student)
        student.groups.add(self.group)

        self.client.force_login(user)
        response = self.client.get(reverse('schedule'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'schedule/student_and_parent_schedule.html')
        self.assertEqual(response.context['schedule_owner_name'], user.get_full_name())

    def test_teacher_sees_own_schedule(self):
        user, teacher = make_user_with_role('teacher1', Teacher)
        self.group.teacher = teacher
        self.group.save()

        self.client.force_login(user)
        response = self.client.get(reverse('schedule'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'schedule/schedule.html')
        self.assertTrue(response.context['is_teacher_view'])

    def test_parent_without_children_gets_permission_denied(self):
        user, parent = make_user_with_role('parent1', Parent)

        self.client.force_login(user)
        response = self.client.get(reverse('schedule'))

        self.assertEqual(response.status_code, 403)

    def test_parent_with_children_sees_first_childs_schedule(self):
        user, parent = make_user_with_role('parent1', Parent)
        child_user, child = make_user_with_role('child1', Student)
        parent.children.add(child)

        self.client.force_login(user)
        response = self.client.get(reverse('schedule'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_child'], child)
        self.assertTrue(response.context['show_combined_score'])

    def test_parent_can_select_specific_child(self):
        user, parent = make_user_with_role('parent1', Parent)
        _child1_user, child1 = make_user_with_role('child1', Student)
        _child2_user, child2 = make_user_with_role('child2', Student)
        parent.children.add(child1, child2)

        self.client.force_login(user)
        response = self.client.get(reverse('schedule'), {'child_id': child2.id})

        self.assertEqual(response.context['selected_child'], child2)

    def test_user_without_role_gets_permission_denied(self):
        user = User.objects.create_user(username='norole1', password='pass12345')

        self.client.force_login(user)
        response = self.client.get(reverse('schedule'))

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('schedule'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)


class GradeLessonParticipationViewTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.teacher_user, self.teacher = make_user_with_role('teacher1', Teacher)
        self.group = Group.objects.create(name='Group A', subject=subject, teacher=self.teacher)
        self.lesson = Lesson.objects.create(
            group=self.group, weekday=0, start_time=time(10, 0), end_time=time(11, 0),
        )
        self.student_user, self.student = make_user_with_role('student1', Student)
        self.student.groups.add(self.group)

    def test_non_teacher_gets_permission_denied(self):
        self.client.force_login(self.student_user)
        response = self.client.get(
            reverse('grade_lesson_participation', args=[self.lesson.id, '2026-07-13'])
        )
        self.assertEqual(response.status_code, 403)

    def test_teacher_of_group_can_view_grading_page(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(
            reverse('grade_lesson_participation', args=[self.lesson.id, '2026-07-13'])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['students_with_scores']), 1)

    def test_teacher_of_other_group_gets_404(self):
        other_teacher_user, _t = make_user_with_role('teacher2', Teacher)
        self.client.force_login(other_teacher_user)

        response = self.client.get(
            reverse('grade_lesson_participation', args=[self.lesson.id, '2026-07-13'])
        )

        self.assertEqual(response.status_code, 404)

    def test_teacher_can_submit_scores(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse('grade_lesson_participation', args=[self.lesson.id, '2026-07-13']),
            {f'score_{self.student.id}': '45'},
        )

        self.assertRedirects(response, reverse('schedule'))
        participation = LessonParticipation.objects.get(
            lesson=self.lesson, lesson_date=date(2026, 7, 13), student=self.student,
        )
        self.assertEqual(participation.score, 45)

    def test_score_is_clamped_between_0_and_50(self):
        self.client.force_login(self.teacher_user)

        self.client.post(
            reverse('grade_lesson_participation', args=[self.lesson.id, '2026-07-13']),
            {f'score_{self.student.id}': '999'},
        )

        participation = LessonParticipation.objects.get(
            lesson=self.lesson, lesson_date=date(2026, 7, 13), student=self.student,
        )
        self.assertEqual(participation.score, 50)

    def test_blank_score_is_skipped(self):
        self.client.force_login(self.teacher_user)

        self.client.post(
            reverse('grade_lesson_participation', args=[self.lesson.id, '2026-07-13']),
            {f'score_{self.student.id}': ''},
        )

        self.assertFalse(
            LessonParticipation.objects.filter(lesson=self.lesson, student=self.student).exists()
        )

    def test_custom_time_makeup_shown_on_grading_page(self):
        from schedule.models import LessonAbsence

        LessonAbsence.objects.create(
            student=self.student,
            lesson=self.lesson,
            missed_date=date(2026, 7, 13),
            makeup_date=date(2026, 7, 15),
            makeup_start_time=time(14, 0),
            makeup_end_time=time(15, 0),
        )

        self.client.force_login(self.teacher_user)
        response = self.client.get(
            reverse('grade_lesson_participation', args=[self.lesson.id, '2026-07-13'])
        )

        item = next(
            i for i in response.context['students_with_scores']
            if i['student'].id == self.student.id
        )
        self.assertIsNotNone(item['custom_makeup'])
        self.assertEqual(item['custom_makeup'].makeup_start_time, time(14, 0))

    def test_visiting_makeup_student_appears_in_roster(self):
        from schedule.models import LessonAbsence

        other_subject = Subject.objects.create(name='Англійська')
        other_teacher_user, other_teacher = make_user_with_role('teacher2', Teacher)
        other_group = Group.objects.create(name='Group B', subject=other_subject, teacher=other_teacher)
        other_lesson = Lesson.objects.create(
            group=other_group, weekday=1, start_time=time(12, 0), end_time=time(13, 0),
        )

        visiting_student_user, visiting_student = make_user_with_role('student2', Student)
        visiting_student.groups.add(other_group)

        LessonAbsence.objects.create(
            student=visiting_student,
            lesson=other_lesson,
            missed_date=date(2026, 7, 14),
            makeup_lesson=self.lesson,
            makeup_date=date(2026, 7, 13),
        )

        self.client.force_login(self.teacher_user)
        response = self.client.get(
            reverse('grade_lesson_participation', args=[self.lesson.id, '2026-07-13'])
        )

        student_ids = {item['student'].id for item in response.context['students_with_scores']}
        self.assertIn(visiting_student.id, student_ids)

        visiting_entry = next(
            item for item in response.context['students_with_scores']
            if item['student'].id == visiting_student.id
        )
        self.assertEqual(visiting_entry['visiting_from'], other_group)

    def test_teacher_can_grade_visiting_makeup_student(self):
        from schedule.models import LessonAbsence

        other_subject = Subject.objects.create(name='Англійська')
        other_teacher_user, other_teacher = make_user_with_role('teacher2', Teacher)
        other_group = Group.objects.create(name='Group B', subject=other_subject, teacher=other_teacher)
        other_lesson = Lesson.objects.create(
            group=other_group, weekday=1, start_time=time(12, 0), end_time=time(13, 0),
        )

        visiting_student_user, visiting_student = make_user_with_role('student2', Student)
        visiting_student.groups.add(other_group)

        LessonAbsence.objects.create(
            student=visiting_student,
            lesson=other_lesson,
            missed_date=date(2026, 7, 14),
            makeup_lesson=self.lesson,
            makeup_date=date(2026, 7, 13),
        )

        self.client.force_login(self.teacher_user)
        response = self.client.post(
            reverse('grade_lesson_participation', args=[self.lesson.id, '2026-07-13']),
            {f'score_{visiting_student.id}': '30'},
        )

        self.assertRedirects(response, reverse('schedule'))
        participation = LessonParticipation.objects.get(
            lesson=self.lesson, lesson_date=date(2026, 7, 13), student=visiting_student,
        )
        self.assertEqual(participation.score, 30)