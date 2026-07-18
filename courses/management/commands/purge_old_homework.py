from django.core.management.base import BaseCommand
from django.utils import timezone

from courses.models import Homework


class Command(BaseCommand):
    help = 'Deletes homework (and its submissions, grades and files) past its deadline by more than the given number of days.'

    def add_arguments(self, parser):
        parser.add_argument('--older-than-days', type=int, default=60)
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        older_than_days = options['older_than_days']
        force = options['force']

        cutoff = timezone.now() - timezone.timedelta(days=older_than_days)
        homeworks = Homework.objects.filter(deadline__lt=cutoff).prefetch_related(
            'files', 'submissions__files'
        )

        count = homeworks.count()

        if count == 0:
            self.stdout.write('Немає ДЗ для видалення.')
            return

        if not force:
            self.stdout.write(f'Знайдено {count} ДЗ для видалення (дедлайн старший за {older_than_days} днів):')
            for homework in homeworks:
                self.stdout.write(f'  - [{homework.id}] "{homework.title}" (група: {homework.group.name}, дедлайн: {homework.deadline:%Y-%m-%d})')
            self.stdout.write('Це був тестовий прогін. Додайте --force, щоб реально видалити.')
            return

        deleted_count = 0
        for homework in homeworks:
            for homework_file in homework.files.all():
                homework_file.file.delete(save=False)

            for submission in homework.submissions.all():
                for submission_file in submission.files.all():
                    submission_file.file.delete(save=False)

            homework.delete()
            deleted_count += 1

        self.stdout.write(self.style.SUCCESS(f'Видалено {deleted_count} ДЗ разом з файлами.'))