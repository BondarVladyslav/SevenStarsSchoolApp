from django.db import models
from users.models import Student,Teacher
from django.core.validators import MaxValueValidator, MinValueValidator

class Subject(models.Model):
    name = models.CharField(max_length=100)

class Level(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='levels')
    name = models.CharField(max_length=50)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ('subject', 'name')
        ordering = ['order']

    def __str__(self):
        return f'{self.subject.name} — {self.name}'
    
class Group(models.Model):
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, related_name='groups')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='groups')
    level = models.ForeignKey(Level, null=True, blank=True, on_delete=models.SET_NULL, related_name='groups')
    def __str__(self):
        return self.name
    

class Homework(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='homeworks')
    lesson = models.ForeignKey('schedule.Lesson', on_delete=models.SET_NULL, null=True, blank=True, related_name='homeworks')
    lesson_date = models.DateField(null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    deadline = models.DateTimeField()
    class Meta:
        ordering = ['id']

class HomeworkFile(models.Model):
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='homework_files/')
    uploaded_at = models.DateTimeField(auto_now_add=True)


class HomeworkSubmission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'перевіряється'),
        ('checked', 'перевірено'),
        ('need_revision', 'потребує виправлень'),
    ]

    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='submissions')
    text = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    teacher_comment = models.TextField(blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    grade = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(50)]
    )

    class Meta:
        unique_together = ('homework', 'student')


class SubmissionFile(models.Model):
    submission = models.ForeignKey(HomeworkSubmission, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='submission_files/')
    uploaded_at = models.DateTimeField(auto_now_add=True)