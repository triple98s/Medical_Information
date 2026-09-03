import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update a superuser from environment variables."

    def handle(self, *args, **options):
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")

        if not email or not password:
            raise CommandError(
                "Set DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD before running this command."
            )

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            email=email,
            defaults={"username": username, "is_staff": True, "is_superuser": True},
        )
        user.username = username
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        message = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f'Admin user "{email}" {message}. Password not displayed.'))
