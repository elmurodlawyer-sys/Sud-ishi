import shutil
import tempfile
from datetime import timedelta

from django.contrib.admin.sites import site
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from core.models import ClassifierKind
from core.testing import cls, make_case, make_court, make_orgs, make_users
from notifications.models import Notification, NotificationKind

from . import services
from . import urls as case_urls
from .models import Case, CaseEvent, Deadline, EventType, Hearing, ReviewStatus, StatusCode


class CaseTestBase(TestCase):
    def setUp(self):
        self.orgs = make_orgs()
        self.users = make_users(self.orgs)
        self.court = make_court()
        self.case = make_case(self.orgs["urgut"], self.users["urgut"], court=self.court, responsible=self.users["urgut"])
        self.other = make_case(self.orgs["buxoro"], self.users["buxoro"], number="2-2002-2601/200")

    def login(self, name):
        self.client.force_login(self.users[name])


class RegistrationTests(CaseTestBase):
    def test_reg_number_status_and_stage(self):
        self.assertRegex(self.case.reg_number, r"^SM-\d{4}-\d{6}$")
        self.assertEqual(self.case.status.code, StatusCode.NEW)
        self.assertEqual(self.case.stages.count(), 1)
        self.assertTrue(self.case.events.filter(event_type=EventType.CREATED).exists())

    def test_duplicate_case_rejected_by_form(self):
        self.login("urgut")
        resp = self.client.post("/ishlar/yangi/", {
            "case_number": "4-1001-2601 / 100", "organization": self.orgs["urgut"].pk, "role": "javobgar", "court": self.court.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "allaqachon ro‘yxatga olingan")
        self.assertEqual(Case.objects.count(), 2)

    def test_create_case_via_form(self):
        self.login("urgut")
        resp = self.client.post("/ishlar/yangi/", {
            "case_number": "2-3003-2601/300", "organization": self.orgs["urgut"].pk, "role": "davogar",
            "plaintiffs": "Urgut Inson markazi", "defendants": "Fuqaro", "court": self.court.pk,
            "instance": cls(ClassifierKind.INSTANCE, "birinchi").pk, "claim_amount": "1000000",
        })
        self.assertEqual(resp.status_code, 302)
        case = Case.objects.get(case_number="2-3003-2601/300")
        self.assertEqual(case.created_by, self.users["urgut"])
        # Yuridik bo'lim yangi ish haqida xabardor qilinadi
        self.assertTrue(Notification.objects.filter(user=self.users["yurist"], case=case, kind=NotificationKind.NEW_CASE).exists())

    def test_org_user_cannot_register_case_for_other_org(self):
        self.login("urgut")
        resp = self.client.post("/ishlar/yangi/", {"case_number": "1-1", "organization": self.orgs["buxoro"].pk, "role": "davogar"})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Case.objects.filter(case_number="1-1").exists())


class PermissionTests(CaseTestBase):
    def test_scope_for_org_users(self):
        self.login("urgut")
        self.assertEqual(self.client.get(self.case.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.other.get_absolute_url()).status_code, 403)
        resp = self.client.get("/ishlar/")
        self.assertContains(resp, self.case.case_number)
        self.assertNotContains(resp, self.other.case_number)

    def test_regional_sees_subordinate_centers(self):
        self.login("samarqand")
        self.assertEqual(self.client.get(self.case.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.other.get_absolute_url()).status_code, 403)

    def test_leadership_views_all_but_cannot_edit(self):
        self.login("rahbar")
        self.assertEqual(self.client.get(self.other.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(f"/ishlar/{self.case.pk}/tahrirlash/").status_code, 403)
        self.assertEqual(self.client.get("/ishlar/yangi/").status_code, 403)

    def test_only_legal_can_cancel_and_approve(self):
        self.login("urgut")
        self.client.post(f"/ishlar/{self.case.pk}/amal/cancel/", {"reason": "takroriy"})
        self.client.post(f"/ishlar/{self.case.pk}/amal/approve/", {"reason": ""})
        self.case.refresh_from_db()
        self.assertFalse(self.case.is_cancelled)
        self.assertNotEqual(self.case.review_status, ReviewStatus.APPROVED)
        self.login("yurist")
        self.client.post(f"/ishlar/{self.case.pk}/amal/cancel/", {"reason": "Takroriy yozuv"})
        self.case.refresh_from_db()
        self.assertTrue(self.case.is_cancelled)
        self.assertEqual(self.case.cancel_reason, "Takroriy yozuv")
        # Bekor qilingan kartochka jismonan o'chirilmaydi va tarixda qoladi
        self.assertTrue(Case.objects.filter(pk=self.case.pk).exists())
        self.assertTrue(self.case.events.filter(event_type=EventType.CANCELLED).exists())

    def test_cancel_requires_reason(self):
        self.login("yurist")
        self.client.post(f"/ishlar/{self.case.pk}/amal/cancel/", {"reason": ""})
        self.case.refresh_from_db()
        self.assertFalse(self.case.is_cancelled)

    def test_no_physical_delete_for_ordinary_staff(self):
        request = RequestFactory().get("/")
        request.user = self.users["yurist"]
        self.users["yurist"].is_staff = True
        self.assertFalse(site._registry[Case].has_delete_permission(request, self.case))
        self.assertFalse(any("delete" in str(p.pattern) or "ochirish" in str(p.pattern) for p in case_urls.urlpatterns))


class WorkflowTests(CaseTestBase):
    def test_status_change_requires_comment_and_is_logged(self):
        self.login("urgut")
        status = cls(ClassifierKind.CASE_STATUS, StatusCode.IN_PROGRESS)
        data = {
            "case_number": self.case.case_number, "organization": self.orgs["urgut"].pk, "role": "javobgar", "court": self.court.pk,
            "instance": self.case.instance_id, "status": status.pk, "responsible": self.users["urgut"].pk,
        }
        resp = self.client.post(f"/ishlar/{self.case.pk}/tahrirlash/", data)
        self.assertContains(resp, "izoh kiritish majburiy")
        data["change_comment"] = "Sud ishni ish yuritishga qabul qildi"
        resp = self.client.post(f"/ishlar/{self.case.pk}/tahrirlash/", data)
        self.assertEqual(resp.status_code, 302)
        event = self.case.events.filter(event_type=EventType.STATUS).first()
        self.assertEqual(event.user, self.users["urgut"])
        self.assertEqual(event.comment, "Sud ishni ish yuritishga qabul qildi")
        # Holat o'zgarganida Yuridik bo'lim emas, tashkilot xodimlari xabardor qilinadi (o'zgartiruvchidan tashqari)
        self.assertTrue(Notification.objects.filter(user=self.users["samarqand"], kind=NotificationKind.STATUS).exists())
        self.assertFalse(Notification.objects.filter(user=self.users["urgut"], kind=NotificationKind.STATUS).exists())

    def test_finished_requires_outcome(self):
        self.login("urgut")
        data = {
            "case_number": self.case.case_number, "organization": self.orgs["urgut"].pk, "role": "javobgar", "court": self.court.pk,
            "status": cls(ClassifierKind.CASE_STATUS, StatusCode.FINISHED).pk, "change_comment": "yakunlandi",
        }
        resp = self.client.post(f"/ishlar/{self.case.pk}/tahrirlash/", data)
        self.assertContains(resp, "yakuniy natija kiritilishi shart")

    def test_org_user_cannot_archive_via_edit(self):
        self.login("urgut")
        data = {
            "case_number": self.case.case_number, "organization": self.orgs["urgut"].pk, "role": "javobgar",
            "status": cls(ClassifierKind.CASE_STATUS, StatusCode.ARCHIVED).pk, "change_comment": "x",
        }
        resp = self.client.post(f"/ishlar/{self.case.pk}/tahrirlash/", data)
        self.assertEqual(resp.status_code, 200)
        self.case.refresh_from_db()
        self.assertEqual(self.case.status.code, StatusCode.NEW)

    def test_new_stage_updates_instance_and_status(self):
        self.login("yurist")
        resp = self.client.post(f"/ishlar/{self.case.pk}/bosqich/", {
            "instance": cls(ClassifierKind.INSTANCE, "apellyatsiya").pk, "started_on": timezone.localdate().isoformat(),
            "note": "Apellyatsiya shikoyati berildi", "case_number": "4-A-1",
        })
        self.assertEqual(resp.status_code, 302)
        self.case.refresh_from_db()
        self.assertEqual(self.case.instance.code, "apellyatsiya")
        self.assertEqual(self.case.status.code, StatusCode.APPEAL)
        self.assertEqual(self.case.stages.count(), 2)
        self.assertEqual(self.case.stages.filter(ended_on__isnull=True).count(), 1)
        self.assertTrue(self.case.events.filter(event_type=EventType.STAGE).exists())

    def test_hearing_postponed_with_next_hearing(self):
        self.login("urgut")
        at = timezone.localtime() + timedelta(days=2)
        self.client.post(f"/ishlar/{self.case.pk}/majlis/", {"scheduled_at": at.strftime("%Y-%m-%dT%H:%M"), "status": "rejalashtirilgan"})
        self.case.refresh_from_db()
        self.assertEqual(self.case.status.code, StatusCode.HEARING_SET)
        hearing = self.case.hearings.get()
        nxt = at + timedelta(days=10)
        self.client.post(f"/ishlar/{self.case.pk}/majlis/{hearing.pk}/", {
            "scheduled_at": at.strftime("%Y-%m-%dT%H:%M"), "status": "qoldirildi",
            "result": cls(ClassifierKind.HEARING_RESULT, "qoldirildi").pk, "next_hearing_at": nxt.strftime("%Y-%m-%dT%H:%M"),
        })
        self.case.refresh_from_db()
        self.assertEqual(self.case.hearings.count(), 2)
        self.assertEqual(timezone.localtime(self.case.next_hearing_at).date(), nxt.date())

    def test_submit_return_approve(self):
        self.login("urgut")
        self.client.post(f"/ishlar/{self.case.pk}/amal/submit/", {"reason": ""})
        self.case.refresh_from_db()
        self.assertEqual(self.case.review_status, ReviewStatus.PENDING)
        self.assertTrue(Notification.objects.filter(user=self.users["yurist"], kind=NotificationKind.REVIEW).exists())
        self.login("yurist")
        self.client.post(f"/ishlar/{self.case.pk}/amal/return/", {"reason": "Da’vo summasini kiriting"})
        self.case.refresh_from_db()
        self.assertEqual(self.case.review_status, ReviewStatus.RETURNED)
        self.assertEqual(self.case.status.code, StatusCode.CLARIFYING)
        self.assertTrue(Notification.objects.filter(user=self.users["urgut"], kind=NotificationKind.RETURNED).exists())

    def test_deadline_and_control_warnings(self):
        Deadline.objects.create(case=self.case, title="Yozma fikr", due_date=timezone.localdate() - timedelta(days=1))
        self.assertIn("Muddati o‘tib ketgan nazorat mavjud.", self.case.control_warnings())
        self.login("urgut")
        self.assertContains(self.client.get("/ishlar/?nazorat=otgan"), self.case.case_number)
        self.assertContains(self.client.get("/ishlar/nazorat/"), "Yozma fikr")


class FilterTests(CaseTestBase):
    def test_filters(self):
        self.login("yurist")
        checks = {
            f"?case_number=4-1001": True, "?role=davogar": False, f"?region={self.orgs['urgut'].region_id}": True,
            f"?organization={self.orgs['samarqand'].pk}&include_children=on": True,
            f"?organization={self.orgs['samarqand'].pk}": False, "?defendant=Urgut": True, "?q=Karimov": True,
            f"?court_type={self.court.court_type_id}": True, "?state=closed": False, "?nazorat=masulsiz": False,
        }
        for query, present in checks.items():
            resp = self.client.get("/ishlar/" + query)
            (self.assertContains if present else self.assertNotContains)(resp, "4-1001-2601/100", msg_prefix=query)

    def test_exports(self):
        self.login("yurist")
        resp = self.client.get("/ishlar/?export=xlsx")
        self.assertEqual(resp["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertTrue(resp.content.startswith(b"PK"))
        resp = self.client.get("/ishlar/?export=pdf")
        self.assertTrue(resp.content.startswith(b"%PDF"))
        self.assertContains(self.client.get("/ishlar/?export=print"), "window.print")


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DocumentTests(CaseTestBase):
    def tearDown(self):
        from django.conf import settings

        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    def test_upload_and_download_with_permissions(self):
        self.login("urgut")
        resp = self.client.post(f"/ishlar/{self.case.pk}/hujjat/", {
            "doc_type": cls(ClassifierKind.DOCUMENT_TYPE, "davo_arizasi").pk, "title": "Da’vo arizasi", "number": "15",
            "file": SimpleUploadedFile("ariza.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        })
        self.assertEqual(resp.status_code, 302)
        doc = self.case.documents.get()
        self.assertEqual((doc.uploaded_by, doc.original_name, doc.number), (self.users["urgut"], "ariza.pdf", "15"))
        resp = self.client.get(f"/ishlar/{self.case.pk}/hujjat/{doc.pk}/")
        self.assertEqual(b"".join(resp.streaming_content), b"%PDF-1.4 test")
        self.login("buxoro")
        self.assertEqual(self.client.get(f"/ishlar/{self.case.pk}/hujjat/{doc.pk}/").status_code, 403)

    def test_rejects_disallowed_extension(self):
        self.login("urgut")
        resp = self.client.post(f"/ishlar/{self.case.pk}/hujjat/", {
            "doc_type": cls(ClassifierKind.DOCUMENT_TYPE, "boshqa").pk, "file": SimpleUploadedFile("x.exe", b"MZ"),
        })
        self.assertContains(resp, "Ruxsat etilmagan fayl turi")


class HistoryTests(CaseTestBase):
    def test_apply_changes_records_diff(self):
        old = services.snapshot(self.case)
        self.case.judge = "Yangi sudya"
        self.case.save()
        changes = services.apply_changes(self.case, self.users["yurist"], old, "izoh")
        self.assertEqual(changes, [{"field": "judge", "label": "Mas’ul sudya", "old": "", "new": "Yangi sudya"}])
        self.assertTrue(CaseEvent.objects.filter(case=self.case, changes__isnull=False, user=self.users["yurist"]).exists())

    def test_hearing_list_page(self):
        Hearing.objects.create(case=self.case, scheduled_at=timezone.now() + timedelta(days=1))
        self.login("samarqand")
        self.assertContains(self.client.get("/ishlar/majlislar/"), self.case.case_number)
        self.login("buxoro")
        self.assertNotContains(self.client.get("/ishlar/majlislar/"), self.case.case_number)
