from django.core.management.base import BaseCommand

from accounts.backup import backup_dir, create_backup


class Command(BaseCommand):
    help = "Ma'lumotlar bazasi va hujjatlarning zaxira nusxasini yaratadi. --keep N — oxirgi N ta nusxani saqlaydi."

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=30)

    def handle(self, *args, **options):
        path = create_backup(label="avtomatik")
        self.stdout.write(self.style.SUCCESS(f"Zaxira nusxa: {path}"))
        files = sorted(backup_dir().glob("sud_monitoringi_*.zip"), reverse=True)
        for old in files[options["keep"]:]:
            old.unlink()
            self.stdout.write(f"Eski nusxa o'chirildi: {old.name}")
