from django import forms
from chat.models import Conversation, Message
from courses.models import HomeworkSubmission, Homework


class HomeworkPostForm(forms.ModelForm):
    deadline = forms.DateTimeField(
        required=True,
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'required': 'required'},
            format='%Y-%m-%dT%H:%M',
        ),
        input_formats=['%Y-%m-%dT%H:%M'],
        error_messages={'required': 'Оберіть дедлайн'},
    )

    class Meta:
        model = Homework
        fields = ('title', 'description', 'deadline')


class HomeworkSubmissionForm(forms.ModelForm):
    class Meta:
        model = HomeworkSubmission
        fields = ('text',)


class CheckSubmissionForm(forms.ModelForm):
    grade = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=50,
        widget=forms.NumberInput(attrs={'min': '0', 'max': '50', 'step': '1'}),
        error_messages={'min_value': 'Оцінка має бути від 0 до 50', 'max_value': 'Оцінка має бути від 0 до 50'}
    )

    class Meta:
        model = HomeworkSubmission
        fields = ('grade', 'status', 'teacher_comment')