from django.core.management.base import BaseCommand, CommandError

from accounts.backup import create_backup, restore_backup


class Command(BaseCommand):
    help = "Zaxira nusxadan (ZIP) ma'lumotlarni tiklaydi. Joriy ma'lumotlar almashtiriladi!"

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--yes", action="store_true", help="Tasdiqlashsiz")

    def handle(self, *args, **options):
        if not options["yes"]:
            answer = input("Joriy ma'lumotlar zaxira nusxadagi holatga almashtiriladi. Davom etish uchun 'ha' deb yozing: ")
            if answer.strip().lower() != "ha":
                raise CommandError("Bekor qilindi.")
        safety = create_backup(label="tiklashdan oldingi avtomatik nusxa")
        self.stdout.write(f"Joriy holat saqlandi: {safety}")
        restore_backup(options["path"])
        self.stdout.write(self.style.SUCCESS("Ma'lumotlar tiklandi."))
