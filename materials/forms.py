from django import forms

from .models import Material


class MaterialEditForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['title', 'description']

