from datetime import datetime
import json
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
import secrets
import string
from schedule.models import LessonParticipation
from chat.forms import SendMessageForm
from chat.models import Conversation
from chat.utils import handle_chat_message
from SevenStarsSchool.storage_utils import build_presigned_uploads, presigned_download_url, validate_uploaded_keys
from courses.forms import CheckSubmissionForm, HomeworkPostForm, HomeworkSubmissionForm
from courses.models import Group, Homework, HomeworkFile, HomeworkSubmission, SubmissionFile
from schedule.utils import get_upcoming_lesson_occurrences
from users.models import Parent, Student, Teacher
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
@login_required
def show_my_groups(request):
    user = request.user
    
    student = Student.objects.filter(user=user).first()
    
    if student:
        submissions = HomeworkSubmission.objects.filter(student=student).order_by('-id')

        my_groups = student.groups.select_related('teacher__user').prefetch_related(
            Prefetch(
                'homeworks',
                queryset=Homework.objects.order_by('-id').prefetch_related(
                    Prefetch('submissions', queryset=submissions, to_attr='student_submissions')
                ),
                to_attr='ordered_homeworks'
            )
        ).all()

        context = {
            'groups': my_groups,
        }
        return render(request, 'courses/my_groups_student.html', context)
    
    teacher = Teacher.objects.filter(user=request.user).first()
    if teacher:
        my_groups = Group.objects.filter(teacher=teacher).select_related('subject').prefetch_related(
            Prefetch('students', queryset=Student.objects.select_related('user')),
            'homeworks',
        )
        context = {
            'groups':my_groups,
        }
        return render(request, 'courses/my_groups_teacher.html', context)
    
    parent = Parent.objects.filter(user = request.user).first()
    if parent:
        return redirect('schedule')
    else:
        return redirect('moderation_dashboard')
            

@login_required
def show_the_group(request, group_id):
    user = request.user
    student = Student.objects.filter(user=user).first()

    group = get_object_or_404(
        Group.objects.select_related('teacher__user'),
        id=group_id
    )

    homeworks = group.homeworks.all().order_by('-id')

    if student:
        if student.groups.filter(pk=group.pk).exists():
            teacher_name = group.teacher.user.get_full_name()

            conversation, created = Conversation.objects.get_or_create(
                teacher=group.teacher,
                student=student,
            )
            message_form, message_sent = handle_chat_message(request, conversation)

            context = {
                'message_form': message_form,
                'homeworks': homeworks,
                'group_name': group.name,
                'conversation_messages': conversation.messages.select_related('sender').order_by('-id')[:100],
                'teacher_name': teacher_name,
                'conversation':conversation
            }
            return render(request, 'courses/one_group_student.html', context)
        raise PermissionDenied

    teacher = Teacher.objects.filter(user=user).first()
    if teacher:
        if teacher.groups.filter(pk=group.pk):
            context = {
                'homeworks': homeworks,
                'group': group,
            }
            return render(request, 'courses/one_group_teacher.html', context)
        raise PermissionDenied



@login_required
def request_submission_upload_urls(request, pk):
    if request.method != 'POST':
        return HttpResponseBadRequest()

    homework = get_object_or_404(Homework, pk=pk)
    student = Student.objects.filter(user=request.user).first()
    if not student or not student.groups.filter(pk=homework.group.pk).exists():
        raise PermissionDenied

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest('Некоректний запит')

    files = payload.get('files', [])

    try:
        uploads = build_presigned_uploads(
            files, prefix='submission_files', max_size=settings.MAX_UPLOAD_SIZE_STUDENT,
        )
    except ValueError as e:
        return HttpResponseBadRequest(str(e))
    except RuntimeError:
        return HttpResponseBadRequest('Пряме завантаження недоступне')

    return JsonResponse({'uploads': uploads})


@login_required
def detail_homework_view(request, pk):
    user = request.user
    homework = get_object_or_404(Homework, pk=pk)

    student = Student.objects.filter(user=user).first()
    if student:
        if not student.groups.filter(pk=homework.group.pk).exists():
            raise PermissionDenied


        submission = HomeworkSubmission.objects.filter(homework=homework, student=student).first()
        conversation, created = Conversation.objects.get_or_create(student=student, teacher=homework.group.teacher)

        homework_form = None
        message_form = SendMessageForm()

        if request.method == 'POST':
            action = request.POST.get('action')

            if action == 'send_homework':
                homework_form = HomeworkSubmissionForm(request.POST)
                uploaded_keys = request.POST.getlist('uploaded_keys')

                try:
                    validate_uploaded_keys(
                        uploaded_keys, prefix='submission_files', max_size=settings.MAX_UPLOAD_SIZE_STUDENT,
                    )
                except ValueError:
                    return HttpResponseBadRequest('Некоректні файли')

                if homework_form.is_valid():
                    submission, created = HomeworkSubmission.objects.get_or_create(
                        homework=homework,
                        student=student,
                        defaults={'text': homework_form.cleaned_data['text']}
                    )
                    if not created:
                        submission.text = homework_form.cleaned_data['text']
                        submission.status = 'pending'
                        submission.save()

                    for key in uploaded_keys:
                        SubmissionFile.objects.create(submission=submission, file=key)

                    return redirect('detail_homework', pk=pk)

            elif action == 'delete_submission':
                if submission and submission.status != 'checked':
                    submission.delete()
                    return redirect('detail_homework', pk=pk)
                return HttpResponse('Не можна видалити перевірену роботу')



        if homework_form is None and not submission:
            homework_form = HomeworkSubmissionForm()

        submission_files = submission.files.all() if submission else None
        homework_files = homework.files.all()
        conversation_messages = conversation.messages.all().prefetch_related('sender').order_by('-id')[:100]
        context = {
            'homework': homework,
            'submission_content': submission,
            'homework_form': homework_form,
            'message_form': message_form,
            'submission_files': submission_files,
            'homework_files': homework_files,
            'conversation_messages': conversation_messages,
            'conversation': conversation,
        }
        
        return render(request, 'courses/detail_homework_student.html', context)
    teacher = Teacher.objects.filter(user = user).first()
    if teacher:
        if not teacher.groups.filter(pk=homework.group.pk).exists():
            raise PermissionDenied

        submissions = homework.submissions.all().prefetch_related('student__user', 'files').order_by('-id')
        context = {
            'submissions': submissions,
            'homework':homework
        }
        return render(request, 'courses/detail_homework_teacher.html', context)


@login_required
def request_homework_upload_urls(request, group_id):
    if request.method != 'POST':
        return HttpResponseBadRequest()

    teacher = Teacher.objects.filter(user=request.user).first()
    if not teacher:
        raise PermissionDenied

    get_object_or_404(Group, id=group_id, teacher=teacher)

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest('Некоректний запит')

    files = payload.get('files', [])

    try:
        uploads = build_presigned_uploads(
            files, prefix='homework_files', max_size=settings.MAX_UPLOAD_SIZE_TEACHER,
        )
    except ValueError as e:
        return HttpResponseBadRequest(str(e))
    except RuntimeError:
        return HttpResponseBadRequest('Пряме завантаження недоступне')

    return JsonResponse({'uploads': uploads})


@login_required
def homework_create_or_edit(request, group_id, homework_id=None):
    teacher = Teacher.objects.filter(user=request.user).first()
    if not teacher:
        raise PermissionDenied
 
    group = get_object_or_404(Group, id=group_id, teacher=teacher)
    homework = get_object_or_404(Homework, id=homework_id, group=group) if homework_id else None
 
    if request.method == 'POST':
        action = request.POST.get('action')
 
        if action == 'delete_file':
            file_id = request.POST.get('file_id')
            homework_file = get_object_or_404(HomeworkFile, id=file_id, homework=homework)
            homework_file.file.delete()
            homework_file.delete()
            return redirect('edit_homework', group_id=group_id, homework_id=homework_id)
 

        elif action == 'save':
            form = HomeworkPostForm(request.POST, instance=homework)
            uploaded_keys = request.POST.getlist('uploaded_keys')
 
            try:
                validate_uploaded_keys(
                    uploaded_keys, prefix='homework_files', max_size=settings.MAX_UPLOAD_SIZE_TEACHER,
                )
            except ValueError:
                return HttpResponseBadRequest('Некоректні файли')
 
            if form.is_valid():
                homework = form.save(commit=False)
                homework.group = group
 
                lesson_occurrence = request.POST.get('lesson_occurrence')
                if lesson_occurrence:
                    lesson_id, date_str = lesson_occurrence.split('_')
                    homework.lesson_id = int(lesson_id)
                    homework.lesson_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                else:
                    homework.lesson = None
                    homework.lesson_date = None
 
                homework.save()
 
                for key in uploaded_keys:
                    HomeworkFile.objects.create(homework=homework, file=key)
 
                return redirect('detail_group', group_id=group_id)
 
        elif action == 'delete':
            homework_id = request.POST.get('homework_id')
            homework = Homework.objects.filter(pk=homework_id, group=group).first()
            if not homework:
                raise Http404
            files = homework.files.all()
            for file in files:
                file.file.delete()
                file.delete()
            homework.delete()
 
            return redirect('detail_group', group_id=group_id)
 
    else:
        form = HomeworkPostForm(instance=homework)
 
    existing_files = homework.files.all() if homework else []
    upcoming_lessons = get_upcoming_lesson_occurrences(group)
 
    context = {
        'form': form,
        'group': group,
        'homework': homework,
        'is_edit': homework is not None,
        'existing_files': existing_files,
        'upcoming_lessons': upcoming_lessons,
    }
    return render(request, 'courses/homework_create_or_edit.html', context)


@login_required
def detail_student(request, group_id, student_id):
    teacher = Teacher.objects.filter(user=request.user).first()
    if not teacher:
        raise PermissionDenied

    group = get_object_or_404(Group, id=group_id, teacher=teacher)
    student = get_object_or_404(Student, id=student_id)

    if not group.students.filter(pk=student.pk).exists():
        raise Http404

    conversation, created = Conversation.objects.get_or_create(
        teacher=teacher,
        student=student,
    )

    new_password = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'reset_password':
            alphabet = string.ascii_letters + string.digits
            new_password = ''.join(secrets.choice(alphabet) for _ in range(10))
            student.user.set_password(new_password)
            student.user.save()

        elif action == 'remove_from_group':
            group.students.remove(student)
            return redirect('detail_group', group_id=group_id)


    form, _ = handle_chat_message(request, conversation)

    group_homeworks = Homework.objects.filter(group=group).select_related('lesson').order_by('-id')

    submissions_by_homework_id = {
        s.homework_id: s
        for s in HomeworkSubmission.objects.filter(student=student, homework__group=group)
    }

    lesson_participations = LessonParticipation.objects.filter(
        student=student,
        lesson__group=group,
    ).select_related('lesson')

    homework_occurrences = set(
        group_homeworks.exclude(lesson__isnull=True).exclude(lesson_date__isnull=True)
        .values_list('lesson_id', 'lesson_date')
    )

    participation_by_occurrence = {
        (p.lesson_id, p.lesson_date): p for p in lesson_participations
    }

    student_homeworks = []
    for homework in group_homeworks:
        lesson_participation = None
        if homework.lesson_id and homework.lesson_date:
            lesson_participation = participation_by_occurrence.get(
                (homework.lesson_id, homework.lesson_date)
            )
        student_homeworks.append({
            'homework': homework,
            'submission': submissions_by_homework_id.get(homework.id),
            'lesson_participation': lesson_participation,
        })

    standalone_lesson_grades = [
        p for p in lesson_participations
        if (p.lesson_id, p.lesson_date) not in homework_occurrences
    ]
    standalone_lesson_grades.sort(key=lambda p: p.lesson_date, reverse=True)

    context = {
        'student_homeworks': student_homeworks,
        'standalone_lesson_grades': standalone_lesson_grades,
        'group': group,
        'student': student,
        'conversation_messages': conversation.messages.select_related('sender').order_by('-id')[:100],
        'form': form,
        'new_password': new_password,
        'conversation': conversation,
    }
    return render(request, 'courses/detail_student.html', context)



@login_required
def detail_submission_view(request, submission_id):
    user = request.user
    submission = get_object_or_404(HomeworkSubmission, id=submission_id)
    homework = submission.homework
    group = homework.group
    
    if not group.teacher or group.teacher.user != user:
        raise Http404


    teacher = group.teacher
    if teacher.user == user:
        conversation, created = Conversation.objects.get_or_create(
        teacher=teacher,
        student=submission.student,
    )
        subission_form = CheckSubmissionForm(instance=submission)
        
        if request.method == 'POST' :
            if request.POST.get('action') == 'check_submission':
                subission_form = CheckSubmissionForm(request.POST, instance=submission)
                if subission_form.is_valid():
                    submission = subission_form.save(commit=False)
                    submission.checked_at = timezone.now()
                    submission.save()
                    return redirect('detail_submission', submission_id=submission_id)
            if request.POST.get('action') == 'send_message':
                message_form, message_sent = handle_chat_message(request, conversation, homework)
                if message_sent:
                    return redirect('detail_submission', submission_id = submission_id)
        
        message_form = SendMessageForm()
        
        context = {
            'submission':submission,
            'homework':homework,
            'submission_form':subission_form,
            'message_form':message_form,
            'conversation_messages': conversation.messages.all().select_related('sender').order_by('-id')[:100],
            'conversation': conversation,
        } 
        return render(request, 'courses/detail_submission.html', context)
@login_required
def download_submission_file(request, file_id):
    submission_file = get_object_or_404(SubmissionFile, id=file_id)
    submission = submission_file.submission

    user = request.user


    student = Student.objects.filter(user=user).first()
    teacher = Teacher.objects.filter(user=user).first()

    is_owner = student and submission.student == student
    is_teacher_of_group = teacher and submission.homework.group.teacher == teacher

    if not (is_owner or is_teacher_of_group):
        raise PermissionDenied

    url = presigned_download_url(submission_file.file)
    return redirect(url)
    


@login_required
def download_homework_file(request, file_id):
    homework_file = get_object_or_404(HomeworkFile, id=file_id)
    homework = homework_file.homework

    user = request.user

    student = Student.objects.filter(user=user).first()
    teacher = Teacher.objects.filter(user=user).first()

    is_student_of_group = student and student.groups.filter(pk=homework.group.pk).exists()
    is_teacher_of_group = teacher and homework.group.teacher == teacher

    if not (is_student_of_group or is_teacher_of_group):
        raise PermissionDenied

    url = presigned_download_url(homework_file.file)
    return redirect(url)