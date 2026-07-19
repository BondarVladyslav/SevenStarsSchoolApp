import json

from django.conf import settings
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

    files = payload.get('files', [])

    if user.is_superuser:
        max_size = None
    elif conversation.teacher.user_id == user.id:
        max_size = settings.MAX_UPLOAD_SIZE_TEACHER
    else:
        max_size = settings.MAX_UPLOAD_SIZE_STUDENT

    try:
        uploads = build_presigned_uploads(files, prefix='chat_files', max_files=1, max_size=max_size)
    except ValueError as e:
        return HttpResponseBadRequest(str(e))
    except RuntimeError:
        return HttpResponseBadRequest('Пряме завантаження недоступне')

    return JsonResponse({'uploads': uploads})