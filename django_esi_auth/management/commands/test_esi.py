from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.module_loading import import_string


# https://docs.djangoproject.com/en/3.2/howto/custom-management-commands/
class Command(BaseCommand):
    help = "Command help text"

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        esi = import_string(settings.DJANGO_ESI_AUTH_PROVIDER)
        public_info = esi.client.Character.get_characters_character_id(character_id=95914159).results()
        print(public_info)
