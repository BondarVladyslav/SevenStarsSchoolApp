"""
Скрипт наповнення БД тестовими даними для платформи мовної школи.

Запуск з кореня проєкту (там же де manage.py):
    python populate.py

Перед запуском переконайся, що:
- .env налаштований і БД доступна
- міграції застосовані (python manage.py migrate)
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')  # заміни на реальне ім'я settings-модуля
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from users.models import Student, Teacher
from courses.models import Subject, Group, Homework, HomeworkSubmission
from chat.models import Conversation, Message

User = get_user_model()


def run():
    print('Очищення старих даних...')
    Message.objects.all().delete()
    Conversation.objects.all().delete()
    HomeworkSubmission.objects.all().delete()
    Homework.objects.all().delete()
    Group.objects.all().delete()
    Subject.objects.all().delete()
    Student.objects.all().delete()
    Teacher.objects.all().delete()
    User.objects.filter(is_superuser=False).delete()

    print('Створення предметів...')
    subjects_data = ['Англійська мова', 'Словацька мова', 'Українська мова']
    subjects = {}
    for name in subjects_data:
        subject = Subject.objects.create(name=name, slug=name.lower().replace(' ', '-'))
        subjects[name] = subject
    print(f'  Створено предметів: {len(subjects)}')

    print('Створення вчителів...')
    teachers_data = [
        ('vchytel_olena', 'Олена', 'Ковальчук'),
        ('vchytel_andriy', 'Андрій', 'Сидоренко'),
    ]
    teachers = {}
    for username, first_name, last_name in teachers_data:
        user = User.objects.create_user(
            username=username,
            password='teacher12345',
            first_name=first_name,
            last_name=last_name,
            email=f'{username}@example.com',
        )
        teacher = Teacher.objects.create(user=user)
        teachers[username] = teacher
    print(f'  Створено вчителів: {len(teachers)}')

    print('Створення груп...')
    groups_data = [
        ('Англійська А1', 'vchytel_olena', 'Англійська мова'),
        ('Англійська B1', 'vchytel_olena', 'Англійська мова'),
        ('Словацька для початківців', 'vchytel_andriy', 'Словацька мова'),
    ]
    groups = {}
    for name, teacher_username, subject_name in groups_data:
        group = Group.objects.create(
            name=name,
            teacher=teachers[teacher_username],
            subject=subjects[subject_name],
        )
        groups[name] = group
    print(f'  Створено груп: {len(groups)}')

    print('Створення учнів...')
    students_data = [
        ('uchen_maria', "Мар'я", 'Бондаренко', ['Англійська А1']),
        ('uchen_petro', 'Петро', 'Іваненко', ['Англійська А1', 'Англійська B1']),
        ('uchen_oksana', 'Оксана', 'Мельник', ['Словацька для початківців']),
        ('uchen_ivan', 'Іван', 'Шевченко', ['Англійська B1']),
    ]
    students = {}
    for username, first_name, last_name, group_names in students_data:
        user = User.objects.create_user(
            username=username,
            password='student12345',
            first_name=first_name,
            last_name=last_name,
            email=f'{username}@example.com',
        )
        student = Student.objects.create(user=user)
        student.groups.set([groups[name] for name in group_names])
        students[username] = student
    print(f'  Створено учнів: {len(students)}')

    print('Створення домашніх завдань...')
    homeworks_data = [
        {
            'group': 'Англійська А1',
            'title': 'Present Simple — вправи 1-10',
            'description': 'Виконати вправи на утворення стверджувальних та заперечних форм Present Simple.',
        },
        {
            'group': 'Англійська А1',
            'title': 'Словниковий запас: родина',
            'description': 'Вивчити слова з теми "Family" та написати 5 речень з новими словами.',
        },
        {
            'group': 'Англійська B1',
            'title': 'Essay: My Future Plans',
            'description': 'Написати есе на 150-200 слів про плани на майбутнє.',
        },
        {
            'group': 'Словацька для початківців',
            'title': 'Базові фрази вітання',
            'description': 'Вивчити базові фрази вітання та прощання, записати аудіо з вимовою.',
        },
    ]

    homeworks = []
    for data in homeworks_data:
        homework = Homework.objects.create(
            group=groups[data['group']],
            title=data['title'],
            description=data['description'],
            deadline=timezone.now() + timedelta(days=7),
        )
        homeworks.append(homework)
    print(f'  Створено домашніх завдань: {len(homeworks)}')

    print('Створення зданих робіт...')
    submissions_data = [
        ('uchen_maria', homeworks[0], 'pending', 'Виконала всі вправи, додаю файл.'),
        ('uchen_petro', homeworks[0], 'checked', 'Готово!'),
        ('uchen_petro', homeworks[2], 'need_revision', 'Написав есе, перевірте будь ласка.'),
        ('uchen_ivan', homeworks[2], 'pending', 'Есе додаю нижче.'),
    ]
    submission_count = 0
    for student_username, homework, status, text in submissions_data:
        submission = HomeworkSubmission.objects.create(
            homework=homework,
            student=students[student_username],
            text=text,
            status=status,
        )
        if status == 'checked':
            submission.teacher_comment = 'Чудова робота, без помилок!'
            submission.checked_at = timezone.now()
            submission.save()
        elif status == 'need_revision':
            submission.teacher_comment = 'Зверни увагу на третій абзац, виправ граматичні помилки.'
            submission.checked_at = timezone.now()
            submission.save()
        submission_count += 1
    print(f'  Створено зданих робіт: {submission_count}')

    print('Створення розмов та повідомлень...')
    conversations_data = [
        ('vchytel_olena', 'uchen_maria', [
            ('uchen_maria', 'Доброго дня! Маю питання щодо домашнього завдання.'),
            ('vchytel_olena', 'Доброго дня! Слухаю вас, що саме незрозуміло?'),
            ('uchen_maria', 'Не зовсім розумію різницю між вправою 3 та 4.'),
        ]),
        ('vchytel_olena', 'uchen_petro', [
            ('vchytel_olena', 'Петре, перевірила твоє есе, є кілька зауважень.'),
            ('uchen_petro', 'Дякую за перевірку! Виправлю до кінця тижня.'),
        ]),
        ('vchytel_andriy', 'uchen_oksana', [
            ('uchen_oksana', 'Доброго вечора! Чи можна перенести заняття на інший час?'),
        ]),
    ]

    conversation_count = 0
    message_count = 0
    for teacher_username, student_username, messages in conversations_data:
        conversation = Conversation.objects.create(
            teacher=teachers[teacher_username],
            student=students[student_username],
        )
        conversation_count += 1
        for sender_username, text in messages:
            sender_user = (
                teachers[sender_username].user
                if sender_username in teachers
                else students[sender_username].user
            )
            Message.objects.create(
                conversation=conversation,
                sender=sender_user,
                text=text,
            )
            message_count += 1
    print(f'  Створено розмов: {conversation_count}, повідомлень: {message_count}')

    print('\nГотово!')
    print(f'Вчителів: {Teacher.objects.count()}')
    print(f'Учнів: {Student.objects.count()}')
    print(f'Предметів: {Subject.objects.count()}')
    print(f'Груп: {Group.objects.count()}')
    print(f'Домашніх завдань: {Homework.objects.count()}')
    print(f'Зданих робіт: {HomeworkSubmission.objects.count()}')
    print(f'Розмов: {Conversation.objects.count()}')
    print(f'Повідомлень: {Message.objects.count()}')
    print('\nПаролі для входу:')
    print('  Вчителі: teacher12345')
    print('  Учні: student12345')


if __name__ == '__main__':
    run()
