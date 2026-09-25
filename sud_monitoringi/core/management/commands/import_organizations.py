from django.core.management.base import BaseCommand

from core.importers import import_organizations


class Command(BaseCommand):
    help = "Tashkilotlar ma'lumotnomasini Excel fayldan import qiladi (ustunlar: core/importers.py)."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, *args, **options):
        with open(options["path"], "rb") as f:
            result = import_organizations(f)
        self.stdout.write(self.style.SUCCESS(f"Yangi: {result['created']}, yangilangan: {result['updated']}"))
        for e in result["errors"]:
            self.stdout.write(self.style.WARNING(e))
