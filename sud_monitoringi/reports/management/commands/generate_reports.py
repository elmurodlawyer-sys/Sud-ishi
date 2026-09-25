from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.models import NotificationKind
from notifications.services import notify
from reports.generation import generate_files, is_due
from reports.models import ReportTemplate


class Command(BaseCommand):
    help = "Davriy hisobot shablonlari bo'yicha hisobotlarni avtomatik shakllantiradi va saqlaydi."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        for template in ReportTemplate.objects.exclude(periodicity=""):
            if not (options["force"] or is_due(template)):
                continue
            scope_user = template.created_by if template.created_by and not template.created_by.is_central else None
            report = generate_files(template.name, template.params, scope_user, template=template, automatic=True)
            template.last_generated_at = timezone.now()
            template.save(update_fields=["last_generated_at"])
            notify(
                template.recipients.filter(is_active=True), NotificationKind.SYSTEM,
                f"Hisobot tayyor: {report.title}", "“Saqlangan hisobotlar” bo‘limidan yuklab oling.",
            )
            self.stdout.write(f"Shakllantirildi: {report.title}")
