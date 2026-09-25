"""Oddiy rejalashtiruvchi: cron bo'lmagan muhitda (masalan, Docker) fon jarayoni sifatida ishga tushiriladi.

* integratsiya manbalari — har daqiqada vaqti kelganlari tekshiriladi;
* eslatmalar — har soatda;
* davriy hisobotlar — har soatda (vaqti kelganlari);
* zaxira nusxa — har kuni BACKUP_HOUR soatida.
"""
import logging
import time

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Integratsiya, eslatmalar, davriy hisobotlar va zaxira nusxalarni jadval asosida bajaradi."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Bir marta bajarib chiqish")
        parser.add_argument("--backup-hour", type=int, default=int(getattr(settings, "BACKUP_HOUR", 2)))

    def _safe(self, name, *args, **kwargs):
        try:
            call_command(name, *args, **kwargs)
        except Exception:  # noqa: BLE001 - bitta vazifa xatosi rejalashtiruvchini to'xtatmaydi
            logger.exception("Vazifa bajarilmadi: %s", name)

    def handle(self, *args, **options):
        last_hourly, last_backup_day = None, None
        while True:
            close_old_connections()
            now = timezone.localtime()
            self._safe("run_integration")
            if last_hourly is None or (now - last_hourly).total_seconds() >= 3600:
                self._safe("send_reminders")
                self._safe("generate_reports")
                last_hourly = now
            if now.hour == options["backup_hour"] and last_backup_day != now.date():
                self._safe("backup")
                last_backup_day = now.date()
            if options["once"]:
                break
            time.sleep(60)
