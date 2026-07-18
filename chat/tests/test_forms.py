from django.test import TestCase

from chat.forms import SendMessageForm


class SendMessageFormTests(TestCase):
    def test_valid_with_text_only(self):
        form = SendMessageForm(data={'text': 'Привіт'})
        self.assertTrue(form.is_valid())

    def test_valid_with_blank_text(self):
        form = SendMessageForm(data={'text': ''})
        self.assertTrue(form.is_valid())

    def test_form_has_no_file_field(self):
        form = SendMessageForm(data={'text': 'Привіт'})
        self.assertNotIn('file', form.fields)