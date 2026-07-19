from django.conf import settings

from SevenStarsSchool.storage_utils import validate_uploaded_keys
from .forms import SendMessageForm
from .models import Message


def handle_chat_message(request, conversation, homework=None):
    if request.method == 'POST' and request.POST.get('action') == 'send_message':
        form = SendMessageForm(request.POST)
        uploaded_key = request.POST.get('uploaded_key', '')

        if uploaded_key:
            if request.user.is_superuser:
                max_size = None
            elif request.user.id == conversation.teacher.user_id:
                max_size = settings.MAX_UPLOAD_SIZE_TEACHER
            else:
                max_size = settings.MAX_UPLOAD_SIZE_STUDENT

            try:
                validate_uploaded_keys([uploaded_key], prefix='chat_files', max_files=1, max_size=max_size)
            except ValueError:
                return form, False

        if form.is_valid():
            text = form.cleaned_data['text'].strip()
            if not text and not uploaded_key:
                return form, False

            message = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                text=text,
                file=uploaded_key,
                homework=homework,
            )
            return SendMessageForm(), True
        return form, False

    return SendMessageForm(), False