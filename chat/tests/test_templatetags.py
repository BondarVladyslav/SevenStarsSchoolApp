from django.test import TestCase

from chat.forms import SendMessageForm
from chat.templatetags.chat_tags import message_form_widget


class MessageFormWidgetTests(TestCase):
    def test_text_field_gets_form_id_prefixed_id_by_default(self):
        form = SendMessageForm()
        context = message_form_widget({}, form)

        self.assertEqual(context['text_field_id'], 'chatMessageForm_text')
        self.assertEqual(form.fields['text'].widget.attrs['id'], 'chatMessageForm_text')

    def test_text_field_id_respects_custom_form_id(self):
        form = SendMessageForm()
        context = message_form_widget({}, form, form_id='submissionChat')

        self.assertEqual(context['text_field_id'], 'submissionChat_text')

    def test_two_widgets_with_different_form_ids_never_collide(self):
        first_context = message_form_widget({}, SendMessageForm(), form_id='chatA')
        second_context = message_form_widget({}, SendMessageForm(), form_id='chatB')

        self.assertNotEqual(first_context['text_field_id'], second_context['text_field_id'])