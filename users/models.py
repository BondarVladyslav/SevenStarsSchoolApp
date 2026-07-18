from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    groups = models.ManyToManyField('courses.Group', related_name='students')

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    def str__(self):
        return self.user.get_full_name()
    
class Parent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    children = models.ManyToManyField(Student, related_name='parents')
