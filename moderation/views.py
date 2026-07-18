from datetime import timedelta
import json
import secrets

from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse
from chat.models import User
from courses.models import Group, Level, Subject
from materials.forms import MaterialEditForm
from materials.models import Material, MaterialFile
from moderation.forms import GroupEditForm, LevelEditForm, ParentEditForm, StudentEditForm, SubjectEditForm, TeacherEditForm
from schedule.models import Lesson, ScheduleException
from users.models import Parent, Student, Teacher
from django.core.exceptions import ValidationError
from django.utils import timezone
import random
import string
from django.db.models import Prefetch 
from courses.models import Group
from users.models import Student, Teacher
from SevenStarsSchool.storage_utils import build_presigned_uploads, validate_uploaded_keys
 
 
@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login')
def moderation_dashboard(request):
    groups = Group.objects.select_related('teacher__user').prefetch_related(
        Prefetch('students', queryset=Student.objects.select_related('user'))
    )
    students = Student.objects.select_related('user').prefetch_related('groups')
    teachers = Teacher.objects.select_related('user').prefetch_related('groups')
 
    context = {
        'groups': groups,
        'students': students,
        'teachers': teachers,
    }
    return render(request, 'moderation/dashboard.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login')
def group_create_or_edit(request, group_id=None):
    group = get_object_or_404(Group, id=group_id) if group_id else None
    students = Student.objects.all()
    form = GroupEditForm(instance=group)
 
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete_group':
            if group:
                group.delete()
            return redirect('moderation_dashboard')
        elif action == 'change_group_name':
            form = GroupEditForm(request.POST, instance=group)
            if form.is_valid():
                group = form.save()
                return redirect('moderation_dashboard')
 
    levels_data = list(Level.objects.select_related('subject').values('id', 'subject_id', 'name'))
 
    context = {
        'form': form,
        'group': group,
        'students': students,
        'levels_json': json.dumps(levels_data).replace('</', '<\\/'),
    }
    return render(request, 'moderation/group_edit_or_create.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login')
def student_edit_or_create(request, student_id=None):
    student = get_object_or_404(Student, id=student_id) if student_id else None
    generated_password = None
    student_form = StudentEditForm(instance=student)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete_student':
            if student:
                student.delete()
            return redirect('moderation_dashboard')

        elif action == 'reset_password':
            if student:
                generated_password = generate_password()
                student.user.set_password(generated_password)
                student.user.save()

        elif action == 'change_student_info':
            student_form = StudentEditForm(request.POST, instance=student)
            if student_form.is_valid():
                is_new = student is None
                if is_new:
                    generated_password = generate_password()
                    new_user = create_user_with_unique_username(
                        student_form.cleaned_data['first_name'],
                        student_form.cleaned_data['last_name'],
                        generated_password,
                    )
                    student_form.instance.user = new_user
                    student = student_form.save()

                    request.session['generated_password_for_student'] = generated_password
                    request.session['generated_password_student_id'] = student.id

                    return redirect('edit_student', student_id=student.id)

                if not is_new:
                    student = student_form.save()
                    return redirect('moderation_dashboard')
                student_form = StudentEditForm(instance=student)

        elif action == 'remove_student_from_group':
            if student:
                group = get_object_or_404(Group, id=request.POST.get('group_id'))
                student.groups.remove(group)
                return redirect('edit_student', student_id=student.id)

        elif action == 'add_student_to_group':
            if student:
                group_id = request.POST.get('group_id')
                if group_id:
                    group = get_object_or_404(Group, id=request.POST.get('group_id'))
                    student.groups.add(group)
                return redirect('edit_student', student_id=student.id)

        elif action == 'add_parent_to_student':
            if student:
                parent_id = request.POST.get('parent_id')
                if parent_id:
                    parent = get_object_or_404(Parent, id=parent_id)
                    student.parents.add(parent)
                return redirect('edit_student', student_id=student.id)

        elif action == 'remove_parent_from_student':
            if student:
                parent = get_object_or_404(Parent, id=request.POST.get('parent_id'))
                student.parents.remove(parent)
                return redirect('edit_student', student_id=student.id)

    if (
        student
        and request.session.get('generated_password_student_id') == student.id
        and 'generated_password_for_student' in request.session
    ):
        generated_password = request.session.pop('generated_password_for_student')
        request.session.pop('generated_password_student_id', None)

    groups_without_student = (
        Group.objects.exclude(students=student).distinct() if student else Group.objects.none()
    )
    parents_without_student = (
        Parent.objects.exclude(children=student).distinct() if student else Parent.objects.none()
    )

    context = {
        'student': student,
        'student_form': student_form,
        'groups_without_student': groups_without_student,
        'parents_without_student': parents_without_student,
        'generated_password': generated_password,
    }
    return render(request, 'moderation/student_edit_or_create.html', context)



@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login')
def parent_edit_or_create(request, parent_id=None):
    parent = get_object_or_404(Parent, id=parent_id) if parent_id else None
    generated_password = None
    form = ParentEditForm(instance=parent)
 
    student_id = request.GET.get('student_id') or request.POST.get('student_id')
 
    def redirect_to_parent(target_parent_id):
        url = reverse('edit_parent', kwargs={'parent_id': target_parent_id})
        if student_id:
            url += f'?student_id={student_id}'
        return redirect(url)
 
    if request.method == 'POST':
        action = request.POST.get('action')
 
        if action == 'delete_parent':
            if parent:
                parent.delete()
            if student_id:
                return redirect('edit_student', student_id=student_id)
            return redirect('moderation_dashboard')
 
        elif action == 'reset_password':
            if parent:
                generated_password = generate_password()
                parent.user.set_password(generated_password)
                parent.user.save()
 
        elif action == 'change_parent_info':
            form = ParentEditForm(request.POST, instance=parent)
            if form.is_valid():
                is_new = parent is None
 
                if is_new:
                    generated_password = generate_password()
                    new_user = create_user_with_unique_username(
                        form.cleaned_data['first_name'],
                        form.cleaned_data['last_name'],
                        generated_password,
                    )
                    form.instance.user = new_user
                    parent = form.save()
 
                    if student_id:
                        student = Student.objects.filter(id=student_id).first()
                        if student:
                            parent.children.add(student)
 
                    request.session['generated_password_for_parent'] = generated_password
                    request.session['generated_password_parent_id'] = parent.id
 
                    return redirect_to_parent(parent.id)
 
                parent = form.save()
 
                if student_id:
                    return redirect('edit_student', student_id=student_id)
                return redirect('moderation_dashboard')
 
        elif action == 'remove_child_from_parent':
            if parent:
                child = get_object_or_404(Student, id=request.POST.get('child_id'))
                parent.children.remove(child)
                return redirect_to_parent(parent.id)
 
        elif action == 'add_child_to_parent':
            if parent:
                child_id = request.POST.get('child_id')
                if child_id:
                    child = get_object_or_404(Student, id=child_id)
                    parent.children.add(child)
                return redirect_to_parent(parent.id)
 
    if (
        parent
        and request.session.get('generated_password_parent_id') == parent.id
        and 'generated_password_for_parent' in request.session
    ):
        generated_password = request.session.pop('generated_password_for_parent')
        request.session.pop('generated_password_parent_id', None)
 
    students_without_parent = (
        Student.objects.exclude(parents=parent).distinct() if parent else Student.objects.none()
    )
 
    context = {
        'parent': parent,
        'form': form,
        'students_without_parent': students_without_parent,
        'generated_password': generated_password,
        'student_id': student_id,
    }
    return render(request, 'moderation/parent_edit_or_create.html', context)
 
 
@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login')
def teacher_edit_or_create(request, teacher_id=None):
    teacher = get_object_or_404(Teacher, id=teacher_id) if teacher_id else None
    generated_password = None
    form = TeacherEditForm(instance=teacher)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete_teacher':
            if teacher:
                teacher.delete()
            return redirect('moderation_dashboard')

        elif action == 'reset_password':
            if teacher:
                generated_password = generate_password()
                teacher.user.set_password(generated_password)
                teacher.user.save()

        elif action == 'change_teacher_info':
            form = TeacherEditForm(request.POST, instance=teacher)
            if form.is_valid():
                is_new = teacher is None

                if is_new:
                    generated_password = generate_password()
                    new_user = create_user_with_unique_username(
                        form.cleaned_data['first_name'],
                        form.cleaned_data['last_name'],
                        generated_password,
                    )
                    form.instance.user = new_user
                    teacher = form.save()

                    request.session['generated_password_for_teacher'] = generated_password
                    request.session['generated_password_teacher_id'] = teacher.id

                    return redirect('edit_teacher', teacher_id=teacher.id)

                teacher = form.save()
                return redirect('moderation_dashboard')

    if (
        teacher
        and request.session.get('generated_password_teacher_id') == teacher.id
        and 'generated_password_for_teacher' in request.session
    ):
        generated_password = request.session.pop('generated_password_for_teacher')
        request.session.pop('generated_password_teacher_id', None)

    context = {
        'teacher': teacher,
        'form': form,
        'generated_password': generated_password,
    }
    return render(request, 'moderation/teacher_edit_or_create.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login')
def manage_group_schedule(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    lessons = Lesson.objects.filter(group=group)
 
    if request.method == 'POST':
        action = request.POST.get('action')
 
        if action == 'add_lesson':
            weekday = request.POST.get('weekday')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
 
            if weekday and start_time and end_time:
                Lesson.objects.create(
                    group=group,
                    weekday=weekday,
                    start_time=start_time,
                    end_time=end_time,
                )
            return redirect('manage_group_schedule', group_id=group.id)
 
        elif action == 'delete_lesson':
            lesson_id = request.POST.get('lesson_id')
            Lesson.objects.filter(id=lesson_id, group=group).delete()
            return redirect('manage_group_schedule', group_id=group.id)
 
    context = {
        'group': group,
        'lessons': lessons,
        'weekday_choices': Lesson.WEEKDAY_CHOICES,
    }
    return render(request, 'moderation/group_schedule.html', context)


def generate_username(first_name, last_name):
    base_username = f"{first_name.lower()}.{last_name.lower()}"
    username = base_username
    counter = 1

    while User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1

    return username


def create_user_with_unique_username(first_name, last_name, password):
    username = generate_username(first_name, last_name)
    return User.objects.create_user(username=username, password=password)

def generate_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login')
def materials_list(request):
    materials = Material.objects.select_related('subject', 'level').prefetch_related('files')
 
    context = {
        'materials': materials,
    }
    return render(request, 'materials/materials_list.html', context)
 
 
@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login')
def request_material_upload_urls(request):
    if request.method != 'POST':
        return HttpResponseBadRequest()

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest('Некоректний запит')

    filenames = payload.get('filenames', [])

    try:
        uploads = build_presigned_uploads(filenames, prefix='materials')
    except ValueError:
        return HttpResponseBadRequest('Некоректна кількість файлів')
    except RuntimeError:
        return HttpResponseBadRequest('Пряме завантаження недоступне')

    return JsonResponse({'uploads': uploads})


@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login')
def material_edit_or_create(request, material_id=None):
    material = get_object_or_404(Material, id=material_id) if material_id else None
    form = MaterialEditForm(instance=material)
 
    if request.method == 'POST':
        action = request.POST.get('action')
 
        if action == 'delete_material':
            if material:
                for f in material.files.all():
                    f.file.delete()
                    f.delete()
                material.delete()
            return redirect('materials_list')
 
        elif action == 'delete_file':
            file_id = request.POST.get('file_id')
            material_file = get_object_or_404(MaterialFile, id=file_id, material=material)
            material_file.file.delete()
            material_file.delete()
            return redirect('edit_material', material_id=material_id)
 
        elif action == 'save':
            form = MaterialEditForm(request.POST, instance=material)
            uploaded_keys = request.POST.getlist('uploaded_keys')

            try:
                validate_uploaded_keys(uploaded_keys, prefix='materials')
            except ValueError:
                return HttpResponseBadRequest('Некоректні файли')

            if form.is_valid():
                material = form.save(commit=False)
 
                subject_id = request.POST.get('subject_id')
                level_id = request.POST.get('level_id')
 
                if level_id:
                    level = get_object_or_404(Level, id=level_id)
                    material.level = level
                    material.subject = level.subject
                elif subject_id:
                    material.subject_id = subject_id
                    material.level = None
                else:
                    return HttpResponseBadRequest('Оберіть предмет')
 
                material.save()
 
                for key in uploaded_keys:
                    MaterialFile.objects.create(material=material, file=key)
 
                return redirect('materials_list')
 
    existing_files = material.files.all() if material else []
    subjects = Subject.objects.all()
    levels = Level.objects.select_related('subject').all()
 
    context = {
        'form': form,
        'material': material,
        'is_edit': material is not None,
        'existing_files': existing_files,
        'subjects': subjects,
        'levels': levels,
    }
    return render(request, 'moderation/materials_edit_or_create.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login')
def subject_edit_or_create(request, subject_id=None):
    subject = get_object_or_404(Subject, id=subject_id) if subject_id else None
    form = SubjectEditForm(instance=subject)
 
    if request.method == 'POST':
        action = request.POST.get('action')
 
        if action == 'delete_subject':
            if subject:
                subject.delete()
            return redirect('moderation_dashboard')
 
        elif action == 'save':
            form = SubjectEditForm(request.POST, instance=subject)
            if form.is_valid():
                subject = form.save(commit=False)
                subject.save()
                return redirect('moderation_dashboard')
 
    levels = subject.levels.all() if subject else []
 
    context = {
        'form': form,
        'subject': subject,
        'is_edit': subject is not None,
        'levels': levels,
    }
    return render(request, 'moderation/subject_edit_or_create.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login')
def level_edit_or_create(request, level_id=None):
    level = get_object_or_404(Level, id=level_id) if level_id else None
 
    subject_id = request.GET.get('subject_id') or request.POST.get('subject_id')
    initial = {}
    if not level and subject_id:
        initial['subject'] = subject_id
 
    form = LevelEditForm(instance=level, initial=initial)
 
    if request.method == 'POST':
        action = request.POST.get('action')
 
        if action == 'delete_level':
            subject_id_for_redirect = level.subject_id if level else None
            if level:
                level.delete()
            if subject_id_for_redirect:
                return redirect('edit_subject', subject_id=subject_id_for_redirect)
            return redirect('moderation_dashboard')
 
        elif action == 'save':
            form = LevelEditForm(request.POST, instance=level)
            if form.is_valid():
                level = form.save()
                return redirect('edit_subject', subject_id=level.subject_id)
 
    context = {
        'form': form,
        'level': level,
        'is_edit': level is not None,
        'subject_id': subject_id,
    }
    return render(request, 'moderation/level_edit_or_create.html', context)

DAYS_RANGE = 30
 
 
def get_nearby_lesson_occurrences(group, days_range=DAYS_RANGE):
    today = timezone.localdate()
    start_date = today - timedelta(days=days_range)
    end_date = today + timedelta(days=days_range)
 
    lessons = list(Lesson.objects.filter(group=group))
 
    already_excepted = set(
        ScheduleException.objects.filter(
            lesson__group=group,
            original_date__gte=start_date,
            original_date__lte=end_date,
        ).values_list('lesson_id', 'original_date')
    )
 
    occurrences = []
    current = start_date
    while current <= end_date:
        weekday = current.weekday()
        for lesson in lessons:
            if lesson.weekday != weekday:
                continue
            if (lesson.id, current) in already_excepted:
                continue
            occurrences.append({'lesson': lesson, 'date': current})
        current += timedelta(days=1)
 
    return occurrences
 
 
@login_required
@user_passes_test(lambda u: u.is_superuser, login_url='login')
def manage_schedule_exceptions(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    exceptions = (
        ScheduleException.objects.filter(lesson__group=group)
        .select_related('lesson')
        .order_by('-original_date')
    )
 
    if request.method == 'POST':
        action = request.POST.get('action')
 
        if action == 'add_exception':
            lesson_occurrence = request.POST.get('lesson_occurrence')
            exception_type = request.POST.get('exception_type')
 
            if not (lesson_occurrence and exception_type):
                return HttpResponseBadRequest('Оберіть заняття')
 
            lesson_id, original_date = lesson_occurrence.split('_')
            lesson = get_object_or_404(Lesson, id=lesson_id, group=group)
 
            exception = ScheduleException(
                lesson=lesson,
                original_date=original_date,
                exception_type=exception_type,
                reason=request.POST.get('reason', ''),
            )
 
            if exception_type == 'rescheduled':
                exception.new_date = request.POST.get('new_date') or None
                exception.new_start_time = request.POST.get('new_start_time') or None
                exception.new_end_time = request.POST.get('new_end_time') or None
 
            try:
                exception.full_clean()
            except ValidationError as e:
                return HttpResponseBadRequest('; '.join(e.messages))
 
            exception.save()
            return redirect('manage_schedule_exceptions', group_id=group.id)
 
        elif action == 'delete_exception':
            exception_id = request.POST.get('exception_id')
            ScheduleException.objects.filter(id=exception_id, lesson__group=group).delete()
            return redirect('manage_schedule_exceptions', group_id=group.id)
 
    context = {
        'group': group,
        'occurrences': get_nearby_lesson_occurrences(group),
        'exceptions': exceptions,
        'days_range':DAYS_RANGE
    }
    return render(request, 'moderation/schedule_exceptions.html', context)