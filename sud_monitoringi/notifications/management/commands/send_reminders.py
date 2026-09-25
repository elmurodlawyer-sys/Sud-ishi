from django.core.management.base import BaseCommand

from notifications.reminders import send_reminders


class Command(BaseCommand):
    help = "Yaqinlashayotgan sud majlislari, muddatlar va o'tib ketgan nazoratlar bo'yicha xabarnomalar yuboradi."

    def handle(self, *args, **options):
        stats = send_reminders()
        self.stdout.write(self.style.SUCCESS(f"Yuborildi: {stats}"))
