import json
from django.conf import settings
from django.utils import timezone
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from chat.models import Conversation, Message
from courses.models import Homework
from django.core.cache import cache
from SevenStarsSchool.storage_utils import validate_uploaded_keys
RATE_LIMIT_MAX_MESSAGES = 10
RATE_LIMIT_WINDOW_SECONDS = 10
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        user = self.scope['user']
        if not user.is_authenticated:
            await self.close()
            return
        allowed = await self.user_can_access_conversation(user)
        if not allowed:
            await self.close()
            return
        
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        if data.get('type') == 'ping':
            await self.send(text_data=json.dumps({'kind': 'pong'}))
            return

        text = (data.get('text') or '').strip()
        homework_id = data.get('homework_id') or None
        file_key = (data.get('file_key') or '').strip()

        allowed = await self.check_rate_limit()
        if not allowed:
            await self.send(text_data=json.dumps({
                'kind': 'error',
                'message': 'Забагато повідомлень. Зачекайте кілька секунд.',
            }))
            return
        if not text and not file_key:
            return

        if file_key:
            key_is_valid = await self.validate_file_key(file_key)
            if not key_is_valid:
                await self.send(text_data=json.dumps({
                    'kind': 'error',
                    'message': 'Не вдалося прикріпити файл.',
                }))
                return
 
        homework = await self.get_conversation_homework(homework_id) if homework_id else None

        message = await self.create_message(text, homework, file_key)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message_id': message.id,
                'sender_id': message.sender_id,
                'sender_name': message.sender.get_full_name() or message.sender.username,
                'text': message.text,
                'has_file': bool(file_key),
                'homework_id': homework.id if homework else None,
                'homework_title': homework.title if homework else None,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))
    @database_sync_to_async
    def user_can_access_conversation(self, user):
        try:
            conversation = Conversation.objects.select_related(
                'teacher__user', 'student__user'
            ).get(pk=self.conversation_id)
        except Conversation.DoesNotExist:
            return False

        if user.id not in (conversation.teacher.user_id, conversation.student.user_id):
            return False

        self.max_upload_size = (
            settings.MAX_UPLOAD_SIZE_TEACHER if user.id == conversation.teacher.user_id
            else settings.MAX_UPLOAD_SIZE_STUDENT
        )
        return True

    @sync_to_async
    def validate_file_key(self, file_key):
        try:
            validate_uploaded_keys([file_key], prefix='chat_files', max_files=1, max_size=self.max_upload_size)
        except ValueError:
            return False
        return True

    @database_sync_to_async
    def create_message(self, text, homework, file_key):
        conversation = Conversation.objects.get(pk=self.conversation_id)
        return Message.objects.create(
            conversation=conversation,
            sender=self.scope['user'],
            text=text,
            file=file_key,
            homework=homework,
        )

    @database_sync_to_async
    def get_conversation_homework(self, homework_id):
        conversation = Conversation.objects.select_related('teacher', 'student').get(pk=self.conversation_id)
        return Homework.objects.filter(
            pk=homework_id,
            group__teacher_id=conversation.teacher_id,
            group__students=conversation.student_id,
        ).first()
    
    
    @sync_to_async
    def check_rate_limit(self):
        user_id = self.scope['user'].id
        cache_key = f'chat_rate_limit_{user_id}'
        now = timezone.now().timestamp()
 
        timestamps = cache.get(cache_key, [])
        timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW_SECONDS]
 
        if len(timestamps) >= RATE_LIMIT_MAX_MESSAGES:
            return False
 
        timestamps.append(now)
        cache.set(cache_key, timestamps, RATE_LIMIT_WINDOW_SECONDS)
        return True