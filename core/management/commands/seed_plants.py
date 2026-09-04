import json
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from core.models import MedicinalPlant


class Command(BaseCommand):
    help = "Load initial plants and synchronize the administrator-maintained plant information."

    def handle(self, *args, **options):
        if not MedicinalPlant.objects.exists():
            call_command("loaddata", "plants")
            self.stdout.write("Initial plant data loaded.")
        else:
            self.stdout.write("Initial plant records already exist.")

        fixture_path = Path(settings.BASE_DIR) / "core" / "fixtures" / "admin_plants.json"
        records = json.loads(fixture_path.read_text(encoding="utf-8"))
        updated = 0
        for record in records:
            local_name = record.pop("local_name")
            MedicinalPlant.objects.update_or_create(
                local_name=local_name,
                defaults={"local_name": local_name, **record},
            )
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Administrator plant information synchronized ({updated} records)."))
