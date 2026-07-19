from django import forms
import courses
from courses.models import Group, Level, Subject
from users.models import Parent, Student, Teacher


class StudentEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label='First name')
    last_name = forms.CharField(max_length=150, label='Last name')

    class Meta:
        model = Student
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name

    def save(self, commit=True):
        student = super().save(commit=False)
        user = student.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            student.save()
        return student
class ParentEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label='First name')
    last_name = forms.CharField(max_length=150, label='Last name')

    class Meta:
        model = Parent
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name

    def save(self, commit=True):
        parent = super().save(commit=False)
        user = parent.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            parent.save()
        return parent
    


class GroupEditForm(forms.ModelForm):
    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.all(),
        empty_label='Обрати вчителя',
        label='Teacher',
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        empty_label='Обрати предмет',
        label='Subject',
    )
    level = forms.ModelChoiceField(
        queryset=Level.objects.select_related('subject').all(),
        required=False,
        empty_label='Без рівня',
        label='Level',
    )
 
    class Meta:
        model = Group
        fields = ['name', 'teacher', 'subject', 'level']
 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher'].label_from_instance = (
            lambda teacher: teacher.user.get_full_name() or str(teacher.user)
        )
        self.fields['subject'].label_from_instance = (
            lambda subject: subject.name
        )
        self.fields['level'].label_from_instance = (
            lambda level: f'{level.subject.name} — {level.name}'
        )
 
    def clean(self):
        cleaned_data = super().clean()
        subject = cleaned_data.get('subject')
        level = cleaned_data.get('level')
 
        if level and subject and level.subject_id != subject.id:
            self.add_error('level', 'Обраний рівень не належить обраному предмету.')
 
        return cleaned_data

class TeacherEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label='First name')
    last_name = forms.CharField(max_length=150, label='Last name')
 
    class Meta:
        model = Teacher
        fields = []
 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
 
    def save(self, commit=True):
        teacher = super().save(commit=False)
        user = teacher.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
 
        if commit:
            user.save()
            teacher.save()
 
        return teacher
    
class SubjectEditForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name']
class LevelEditForm(forms.ModelForm):
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        empty_label='Обрати предмет',
        label='Subject',
    )
 
    class Meta:
        model = Level
        fields = ['subject', 'name', 'order']
 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subject'].label_from_instance = lambda subject: subject.name