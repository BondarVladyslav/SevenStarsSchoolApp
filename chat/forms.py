from django import forms

from chat.models import Message


class SendMessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['text']