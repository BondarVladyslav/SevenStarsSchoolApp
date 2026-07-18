from django.db import models
from django.core.exceptions import ValidationError
from users.models import Student
from django.core.validators import MaxValueValidator, MinValueValidator
class Lesson(models.Model):
    WEEKDAY_CHOICES = [
        (0, 'Понеділок'),
        (1, 'Вівторок'),
        (2, 'Середа'),
        (3, 'Четвер'),
        (4, "П'ятниця"),
        (5, 'Субота'),
        (6, 'Неділя'),
    ]
    group = models.ForeignKey('courses.Group', on_delete=models.CASCADE, related_name='lessons')
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    class Meta:
        ordering = ['weekday', 'start_time']

        
class LessonAbsence(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='missed_lessons')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='absences')
    missed_date = models.DateField()

    makeup_lesson = models.ForeignKey(
        Lesson, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='makeup_absences',
    )
    makeup_date = models.DateField(null=True, blank=True)
    makeup_start_time = models.TimeField(null=True, blank=True)
    makeup_end_time = models.TimeField(null=True, blank=True)

    reason = models.CharField(max_length=255, blank=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'lesson', 'missed_date')

    def clean(self):
        if self.makeup_lesson_id and (self.makeup_start_time or self.makeup_end_time):
            raise ValidationError(
                'Оберіть щось одне: або приєднання до наявного заняття (makeup_lesson), '
                'або довільний час (makeup_start_time/makeup_end_time) — не обидва разом.'
            )

    @property
    def resolved_start_time(self):
        return self.makeup_lesson.start_time if self.makeup_lesson_id else self.makeup_start_time

    @property
    def resolved_end_time(self):
        return self.makeup_lesson.end_time if self.makeup_lesson_id else self.makeup_end_time

    def __str__(self):
        return f'{self.student} — {self.lesson} ({self.missed_date})'
    

class ScheduleException(models.Model):
    EXCEPTION_TYPES = [
        ('cancelled', 'Скасовано'),
        ('rescheduled', 'Перенесено'),
    ]

    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='exceptions')
    original_date = models.DateField()
    exception_type = models.CharField(max_length=20, choices=EXCEPTION_TYPES)

    new_date = models.DateField(null=True, blank=True)
    new_start_time = models.TimeField(null=True, blank=True)
    new_end_time = models.TimeField(null=True, blank=True)

    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('lesson', 'original_date')

    def clean(self):
        if self.exception_type == 'rescheduled' and not self.new_date:
            raise ValidationError('Для перенесення потрібна нова дата.')
        if self.exception_type == 'cancelled' and (self.new_date or self.new_start_time):
            raise ValidationError('Скасоване заняття не повинно мати нової дати чи часу.')

class LessonParticipation(models.Model):
    lesson = models.ForeignKey('schedule.Lesson', on_delete=models.CASCADE, related_name='participations')
    lesson_date = models.DateField()
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='lesson_participations')
    score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
    )
 
    class Meta:
        unique_together = ('lesson', 'lesson_date', 'student')
 
    def __str__(self):
        return f'{self.student} — {self.lesson} ({self.lesson_date})'