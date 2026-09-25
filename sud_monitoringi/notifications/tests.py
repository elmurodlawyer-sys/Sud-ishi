from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from cases.models import Deadline, Hearing
from core.testing import make_case, make_orgs, make_users

from .models import Notification, NotificationKind
from .reminders import send_reminders
from .services import notify_case


class ReminderTests(TestCase):
    def setUp(self):
        self.orgs = make_orgs()
        self.users = make_users(self.orgs)
        self.case = make_case(self.orgs["urgut"], responsible=self.users["urgut"])
        self.orphan = make_case(self.orgs["agency"], number="9-9")

    def test_reminders_are_sent_once(self):
        Hearing.objects.create(case=self.case, scheduled_at=timezone.now() + timedelta(days=1))
        Deadline.objects.create(case=self.case, title="Yozma fikr", due_date=timezone.localdate() + timedelta(days=2))
        Deadline.objects.create(case=self.case, title="Eski", due_date=timezone.localdate() - timedelta(days=2))
        send_reminders()
        first = Notification.objects.count()
        send_reminders()
        self.assertEqual(Notification.objects.count(), first)
        urgut = Notification.objects.filter(user=self.users["urgut"])
        self.assertTrue(urgut.filter(kind=NotificationKind.HEARING_SOON).exists())
        self.assertTrue(urgut.filter(kind=NotificationKind.DEADLINE_SOON).exists())
        self.assertTrue(urgut.filter(kind=NotificationKind.OVERDUE).exists())
        # Muddat o'tganda Yuridik bo'lim ham xabardor qilinadi
        self.assertTrue(Notification.objects.filter(user=self.users["yurist"], kind=NotificationKind.OVERDUE).exists())
        self.assertFalse(Notification.objects.filter(user=self.users["buxoro"]).exists())

    def test_fallback_to_legal_when_no_org_users(self):
        notify_case(self.orphan, NotificationKind.STATUS, "Sinov")
        self.assertTrue(Notification.objects.filter(user=self.users["yurist"], title="Sinov").exists())

    @override_settings(EMAIL_NOTIFICATIONS=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_copy(self):
        notify_case(self.case, NotificationKind.STATUS, "Holat o‘zgardi")
        self.assertTrue(any("urgut@example.uz" in m.to for m in mail.outbox))
        self.assertTrue(Notification.objects.filter(user=self.users["urgut"], emailed=True).exists())

    def test_list_and_open(self):
        notify_case(self.case, NotificationKind.STATUS, "Holat")
        n = Notification.objects.get(user=self.users["urgut"])
        self.client.force_login(self.users["urgut"])
        self.assertContains(self.client.get("/xabarnomalar/"), "Holat")
        resp = self.client.get(f"/xabarnomalar/{n.pk}/")
        self.assertRedirects(resp, self.case.get_absolute_url())
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        self.client.force_login(self.users["buxoro"])
        self.assertEqual(self.client.get(f"/xabarnomalar/{n.pk}/").status_code, 404)
