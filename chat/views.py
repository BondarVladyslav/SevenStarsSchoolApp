import json

from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from SevenStarsSchool.storage_utils import build_presigned_uploads, presigned_download_url
from .models import Conversation, Message

@login_required
def download_chat_file(request, message_id):
    message = get_object_or_404(Message, id=message_id)
    conversation = message.conversation
    user = request.user

    is_participant = (
        conversation.student.user_id == user.id
        or conversation.teacher.user_id == user.id
    )

    if not (is_participant or user.is_superuser):
        raise Http404
    url = presigned_download_url(message.file)
    return redirect(url)


@login_required
def request_chat_upload_url(request, conversation_id):
    if request.method != 'POST':
        return HttpResponseBadRequest()

    conversation = get_object_or_404(Conversation, id=conversation_id)
    user = request.user

    is_participant = (
        conversation.student.user_id == user.id
        or conversation.teacher.user_id == user.id
    )

    if not (is_participant or user.is_superuser):
        raise Http404

    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest('Некоректний запит')

    filenames = payload.get('filenames', [])

    try:
        uploads = build_presigned_uploads(filenames, prefix='chat_files', max_files=1)
    except ValueError:
        return HttpResponseBadRequest('Некоректна кількість файлів')
    except RuntimeError:
        return HttpResponseBadRequest('Пряме завантаження недоступне')

    return JsonResponse({'uploads': uploads})