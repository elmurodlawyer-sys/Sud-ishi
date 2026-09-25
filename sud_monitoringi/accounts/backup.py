"""Ma'lumotlarning zaxira nusxasini yaratish va tiklash (6 va 10-bo'limlar).

Zaxira nusxa — ZIP arxiv: bazadagi barcha ma'lumotlar (data.json, SQLite va
PostgreSQL uchun bir xil format) hamda yuklangan hujjatlar (media/).
"""
import io
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone

EXCLUDE = ["contenttypes", "auth.permission", "sessions", "admin.logentry"]


def backup_dir():
    path = Path(settings.BACKUP_ROOT)
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_backup(label="qo'lda"):
    stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    target = backup_dir() / f"sud_monitoringi_{stamp}.zip"
    buffer = io.StringIO()
    call_command("dumpdata", exclude=EXCLUDE, natural_foreign=True, indent=None, stdout=buffer)
    media_root = Path(settings.MEDIA_ROOT)
    files = 0
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.json", buffer.getvalue())
        if media_root.exists():
            for path in media_root.rglob("*"):
                if path.is_file():
                    zf.write(path, f"media/{path.relative_to(media_root).as_posix()}")
                    files += 1
        zf.writestr("manifest.json", json.dumps({
            "created_at": timezone.now().isoformat(), "label": label, "media_files": files,
            "database": settings.DATABASES["default"]["ENGINE"],
        }, ensure_ascii=False))
    return target


def list_backups():
    items = []
    for path in sorted(backup_dir().glob("sud_monitoringi_*.zip"), reverse=True):
        items.append({"name": path.name, "size": path.stat().st_size, "created": datetime.fromtimestamp(
            path.stat().st_mtime, tz=timezone.get_current_timezone())})
    return items


def resolve_backup(name):
    path = (backup_dir() / os.path.basename(name)).resolve()
    if not path.exists() or path.parent != backup_dir().resolve() or path.suffix != ".zip":
        raise FileNotFoundError(name)
    return path


def restore_backup(path):
    """Joriy ma'lumotlarni zaxira nusxadagi holatga qaytaradi."""
    path = Path(path)
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if "data.json" not in names:
            raise ValueError("Arxivda data.json topilmadi — bu tizim zaxira nusxasi emas.")
        data = zf.read("data.json")
        tmp = backup_dir() / f".restore_{timezone.now():%Y%m%d%H%M%S}.json"
        tmp.write_bytes(data)
        try:
            with transaction.atomic():
                call_command("flush", interactive=False, verbosity=0)
                call_command("loaddata", str(tmp), verbosity=0)
        finally:
            tmp.unlink(missing_ok=True)
        media_root = Path(settings.MEDIA_ROOT).resolve()
        for name in names:
            if name.startswith("media/") and not name.endswith("/"):
                target = (media_root / name[len("media/"):]).resolve()
                if not str(target).startswith(str(media_root)):
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(name))
