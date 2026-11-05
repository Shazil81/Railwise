"""Explicit local-only demo setup; normal catalogue seeding never resets accounts."""
import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create the local non-staff demo account using DEMO_PASSWORD. Requires DEBUG=True.'

    def handle(self,*args,**options):
        if not settings.DEBUG:
            raise CommandError('Demo account setup is available only with DEBUG=True.')
        password=os.environ.get('DEMO_PASSWORD')
        if not password:
            raise CommandError('Set DEMO_PASSWORD in your local environment first.')
        user,created=get_user_model().objects.get_or_create(username='demo')
        if not created:
            raise CommandError('The demo account already exists. Use normal password recovery; no credentials were changed.')
        user.set_password(password)
        user.save(update_fields=['password'])
        self.stdout.write(self.style.SUCCESS('Created local non-staff demo account.'))
