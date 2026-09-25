import shutil
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from cases.models import Case
from core.testing import PASSWORD, make_case, make_orgs, make_users

from .backup import create_backup, restore_backup
from .models import AuditLog


class AuthTests(TestCase):
    def setUp(self):
        self.orgs = make_orgs()
        self.users = make_users(self.orgs)

    def test_login_required(self):
        resp = self.client.get("/ishlar/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/tizim/kirish/", resp["Location"])

    def test_login_logged_and_lockout(self):
        self.assertTrue(self.client.login(username="urgut", password=PASSWORD))
        self.assertTrue(AuditLog.objects.filter(username="urgut", action="kirish").exists())
        self.client.logout()
        for _ in range(5):
            self.client.post("/tizim/kirish/", {"username": "urgut", "password": "xato"})
        resp = self.client.post("/tizim/kirish/", {"username": "urgut", "password": PASSWORD})
        self.assertContains(resp, "Ko‘p marta noto‘g‘ri parol")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_write_actions_are_audited(self):
        case = make_case(self.orgs["urgut"])
        self.client.force_login(self.users["yurist"])
        self.client.post(f"/ishlar/{case.pk}/amal/approve/", {"reason": "ok"})
        self.assertTrue(AuditLog.objects.filter(username="yurist", action="ish_approve").exists())

    def test_admin_pages_restricted(self):
        self.client.force_login(self.users["yurist"])
        for url in ("/tizim/foydalanuvchilar/", "/tizim/zaxira/", "/tizim/jurnal/"):
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.client.force_login(self.users["admin"])
        for url in ("/tizim/foydalanuvchilar/", "/tizim/zaxira/", "/tizim/jurnal/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_admin_creates_user_with_role(self):
        self.client.force_login(self.users["admin"])
        resp = self.client.post("/tizim/foydalanuvchilar/yangi/", {
            "username": "yangi", "last_name": "Yangi", "first_name": "Xodim", "role": "inson",
            "is_active": "on", "password1": "Kuchli-Parol-77", "password2": "Kuchli-Parol-77",
        })
        self.assertContains(resp, "tashkilot ko‘rsatilishi shart")
        resp = self.client.post("/tizim/foydalanuvchilar/yangi/", {
            "username": "yangi", "last_name": "Yangi", "first_name": "Xodim", "role": "inson", "organization": self.orgs["urgut"].pk,
            "is_active": "on", "password1": "Kuchli-Parol-77", "password2": "Kuchli-Parol-77",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(self.client.login(username="yangi", password="Kuchli-Parol-77"))
        self.assertTrue(AuditLog.objects.filter(action="foydalanuvchi_saqlandi", is_admin_action=True).exists())


class BackupTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.override = override_settings(BACKUP_ROOT=self.tmp / "b", MEDIA_ROOT=self.tmp / "m")
        self.override.enable()
        (self.tmp / "m" / "case_documents").mkdir(parents=True)
        (self.tmp / "m" / "case_documents" / "a.pdf").write_bytes(b"%PDF")

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_backup_and_restore_roundtrip(self):
        orgs = make_orgs()
        make_users(orgs)
        case = make_case(orgs["urgut"])
        path = create_backup()
        self.assertTrue(path.exists())
        Case.objects.all().delete()
        (self.tmp / "m" / "case_documents" / "a.pdf").unlink()
        restore_backup(path)
        restored = Case.objects.get()
        self.assertEqual((restored.pk, restored.reg_number), (case.pk, case.reg_number))
        self.assertTrue((self.tmp / "m" / "case_documents" / "a.pdf").exists())
