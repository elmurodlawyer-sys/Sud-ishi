from django.core.management.base import BaseCommand

from integration.models import IntegrationSource
from integration.services import due_sources, run_source


class Command(BaseCommand):
    help = "Integratsiya manbalarini tekshiradi (vaqti kelganlarini yoki --all bilan barchasini)."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Davriylikdan qat'i nazar barcha faol manbalar")
        parser.add_argument("--source", type=int, help="Faqat ko'rsatilgan ID dagi manba")

    def handle(self, *args, **options):
        if options.get("source"):
            sources = IntegrationSource.objects.filter(pk=options["source"])
        elif options.get("all"):
            sources = IntegrationSource.objects.filter(is_active=True).exclude(adapter="file")
        else:
            sources = list(due_sources())
        for source in sources:
            run = run_source(source)
            self.stdout.write(f"{source.name}: {source.last_status}")
            if run.errors:
                self.stdout.write(self.style.WARNING(run.errors[:2000]))
