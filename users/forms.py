from django import forms

class LoginUserForm(forms.Form):
    username = forms.CharField(label='Логін')
    password = forms.CharField(label='Пароль')