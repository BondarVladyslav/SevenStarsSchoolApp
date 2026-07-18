from django.db import models

from courses.models import Subject, Level


class Material(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='materials')
    level = models.ForeignKey(Level, null=True, blank=True, on_delete=models.CASCADE, related_name='materials')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class MaterialFile(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='materials/')
    uploaded_at = models.DateTimeField(auto_now_add=True)