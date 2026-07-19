from django import template
from django.conf import settings

from users.models import Teacher

register = template.Library()


@register.inclusion_tag('chat/partials/message_form.html', takes_context=True)
def message_form_widget(context, form, file_chip_id='fileNameChip', max_height=240, homework_id=None, conversation_id=None, form_id='chatMessageForm'):
    request = context.get('request')
    text_field_id = f'{form_id}_text'
    form.fields['text'].widget.attrs['id'] = text_field_id

    max_file_size = settings.MAX_UPLOAD_SIZE_STUDENT
    if request and request.user.is_authenticated:
        if request.user.is_superuser:
            max_file_size = None
        elif Teacher.objects.filter(user=request.user).exists():
            max_file_size = settings.MAX_UPLOAD_SIZE_TEACHER

    return {
        'request': request,
        'csrf_token': context.get('csrf_token'),
        'message_form': form,
        'file_chip_id': file_chip_id,
        'max_height': max_height,
        'homework_id': homework_id,
        'conversation_id': conversation_id,
        'form_id': form_id,
        'text_field_id': text_field_id,
        'current_user_id': request.user.id if request and request.user.is_authenticated else None,
        'max_file_size': max_file_size,
    }


@register.inclusion_tag('chat/partials/chat_messages.html', takes_context=True)
def chat_messages_widget(context, messages, container_id='chatMessages'):
    return {
        'request': context.get('request'),
        'conversation_messages': messages,
        'container_id': container_id,
    }