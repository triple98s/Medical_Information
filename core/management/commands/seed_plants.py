from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.models import MedicinalPlant


class Command(BaseCommand):
    help = "Seed the initial medicinal-plant records if the database is empty."

    def handle(self, *args, **options):
        if MedicinalPlant.objects.exists():
            self.stdout.write("Plant data already exists; skipping seed.")
            return

        call_command("loaddata", "plants")
        self.stdout.write(self.style.SUCCESS("Initial plant data loaded."))
