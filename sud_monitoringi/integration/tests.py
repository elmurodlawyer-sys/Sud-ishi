from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from cases.models import Case, CaseSource, Hearing, ProceduralRole
from core.testing import make_orgs, make_users
from notifications.models import Notification, NotificationKind

from .adapters import parse_html_tables, parse_uploaded_file
from .matching import OrganizationMatcher
from .models import AdapterType, IntegrationSource, RunStatus
from .services import run_source


def record(**kwargs):
    at = (timezone.localtime() + timedelta(days=5)).replace(hour=10, minute=0, second=0, microsecond=0)
    base = {
        "external_key": "", "case_number": "2-1203-2601/555", "court_name": "Fuqarolik ishlari bo‘yicha Urgut tumanlararo sudi",
        "court_type": "Fuqarolik", "region": "Samarqand viloyati", "instance": "Birinchi instansiya", "category": "Mehnat nizolari",
        "plaintiffs": "Karimov Anvar", "defendants": "Ургут тумани Инсон ижтимоий хизматлар маркази", "third_parties": "",
        "judge": "A. Xolmatov", "hearing_at": at.strftime("%Y-%m-%dT%H:%M"), "location": "3-zal", "subject": "Ishga tiklash",
        "claim_amount": "12 500 000", "url": "",
    }
    base.update(kwargs)
    return base


class MatcherTests(TestCase):
    def setUp(self):
        self.orgs = make_orgs()

    def test_matches_cyrillic_alt_name_as_defendant(self):
        result = OrganizationMatcher().match(record())
        self.assertEqual(result.primary.organization, self.orgs["urgut"])
        self.assertEqual(result.primary.role, ProceduralRole.DEFENDANT)

    def test_matches_stir_and_plaintiff(self):
        result = OrganizationMatcher().match(record(plaintiffs="Tashkilot (STIR 301234567)", defendants="Karimov A."))
        self.assertEqual(result.primary.organization, self.orgs["samarqand"])
        self.assertEqual(result.primary.role, ProceduralRole.PLAINTIFF)

    def test_most_specific_org_is_primary(self):
        rec = record(defendants="Urgut tumani “Inson” ijtimoiy xizmatlar markazi",
                     third_parties="Ijtimoiy himoya milliy agentligining Samarqand viloyati boshqarmasi")
        result = OrganizationMatcher().match(rec)
        self.assertEqual(result.primary.organization, self.orgs["urgut"])
        self.assertEqual([m.organization for m in result.others], [self.orgs["samarqand"]])
        self.assertEqual(result.others[0].role, ProceduralRole.THIRD_PARTY)

    def test_no_match_for_unrelated_parties(self):
        self.assertIsNone(OrganizationMatcher().match(record(defendants="“Sharq qurilish” AJ")))

    def test_shared_generic_alt_name_is_ignored(self):
        for org in (self.orgs["urgut"], self.orgs["buxoro"]):
            org.alt_names += "\nIjtimoiy xizmatlar markazi"
            org.save()
        self.assertIsNone(OrganizationMatcher().match(record(defendants="Ijtimoiy xizmatlar markazi")))


class IntegrationProcessTests(TestCase):
    def setUp(self):
        self.orgs = make_orgs()
        self.users = make_users(self.orgs)
        self.source = IntegrationSource.objects.create(name="Sinov", adapter=AdapterType.FILE)

    def test_creates_card_with_hearing_and_notifies(self):
        run = run_source(self.source, records=[record(), record(case_number="9-1", defendants="Boshqa tashkilot")])
        self.assertEqual((run.status, run.fetched, run.matched, run.created), (RunStatus.SUCCESS, 2, 1, 1))
        case = Case.objects.get()
        self.assertEqual(case.organization, self.orgs["urgut"])
        self.assertEqual(case.source, CaseSource.INTEGRATION)
        self.assertEqual(case.claim_amount, 12_500_000)
        self.assertEqual(case.court.court_type.code, "fuqarolik")
        self.assertEqual(case.category.code, "mehnat")
        self.assertEqual(case.status.code, "majlis_tayinlangan")
        self.assertIsNotNone(case.next_hearing_at)
        notified = set(Notification.objects.filter(kind=NotificationKind.NEW_CASE).values_list("user__username", flat=True))
        # Tegishli tashkilot, uning yuqori tashkiloti va Yuridik bo'lim xabardor qilinadi; boshqa hudud — yo'q
        self.assertEqual(notified, {"urgut", "samarqand", "yurist"})

    def test_repeat_detection_does_not_duplicate_and_tracks_changes(self):
        run_source(self.source, records=[record()])
        run = run_source(self.source, records=[record()])
        self.assertEqual((run.created, run.updated, run.unchanged), (0, 0, 1))
        new_time = (timezone.localtime() + timedelta(days=9)).replace(hour=14, minute=30, second=0, microsecond=0)
        run = run_source(self.source, records=[record(hearing_at=new_time.strftime("%Y-%m-%dT%H:%M"), judge="S. Nazarova")])
        self.assertEqual((run.created, run.updated), (0, 1))
        self.assertEqual(Case.objects.count(), 1)
        case = Case.objects.get()
        self.assertEqual(case.judge, "S. Nazarova")
        self.assertEqual(Hearing.objects.filter(case=case).count(), 1)
        self.assertEqual(timezone.localtime(case.hearings.get().scheduled_at), new_time)
        descriptions = " | ".join(case.events.values_list("description", flat=True))
        self.assertIn("Sud majlisi sanasi o‘zgardi", descriptions)
        self.assertIn("Mas’ul sudya", descriptions)

    def test_same_case_from_other_source_is_not_duplicated(self):
        run_source(self.source, records=[record()])
        other = IntegrationSource.objects.create(name="Boshqa", adapter=AdapterType.FILE)
        run = run_source(other, records=[record(case_number="2-1203-2601 / 555")])
        self.assertEqual(run.created, 0)
        self.assertEqual(Case.objects.count(), 1)

    def test_adapter_failure_does_not_break(self):
        source = IntegrationSource.objects.create(name="Ishlamaydigan", adapter=AdapterType.JSON_API, base_url="http://127.0.0.1:9/api")
        run = run_source(source)
        self.assertEqual(run.status, RunStatus.FAILED)
        self.assertIn("ulanib bo‘lmadi", run.errors)
        source.refresh_from_db()
        self.assertIsNotNone(source.last_run_at)
        self.assertIsNone(source.last_success_at)

    def test_demo_adapter(self):
        source = IntegrationSource.objects.create(name="Demo", adapter=AdapterType.DEMO, config={"count": 10})
        run = run_source(source)
        self.assertEqual(run.status, RunStatus.SUCCESS)
        self.assertEqual(run.fetched, 10)
        self.assertEqual(Case.objects.count(), run.created)


class ParsingTests(TestCase):
    def test_html_table(self):
        html = """
        <html><body><table>
          <tr><th>№</th><th>Иш рақами</th><th>Даъвогар</th><th>Жавобгар</th><th>Судья</th><th>Вақти</th></tr>
          <tr><td>1</td><td><a href="/case/77">2-1203-2601/555</a></td><td>Каримов А.</td>
              <td>Ургут тумани Инсон<br>ижтимоий хизматлар маркази</td><td>А. Холматов</td><td>10:30</td></tr>
        </table></body></html>"""
        day = timezone.localdate()
        rows = parse_html_tables(html, "https://jadval2.sud.uz/list", default_date=day, court_name="Urgut sudi")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["case_number"], "2-1203-2601/555")
        self.assertEqual(row["court_name"], "Urgut sudi")
        self.assertEqual(row["url"], "https://jadval2.sud.uz/case/77")
        self.assertEqual(row["hearing_at"], f"{day.isoformat()}T10:30")
        self.assertIn("маркази", row["defendants"])

    def test_csv_upload(self):
        content = "Ish raqami;Da’vogar;Javobgar;Sud nomi;Majlis vaqti\n2-1/1;Karimov;Urgut tumani Inson markazi;Urgut sudi;01.10.2026 10:00\n"
        rows = parse_uploaded_file(SimpleUploadedFile("jadval.csv", content.encode("utf-8")))
        self.assertEqual(rows[0]["case_number"], "2-1/1")
        self.assertEqual(rows[0]["court_name"], "Urgut sudi")
        self.assertEqual(rows[0]["hearing_at"], "2026-10-01T10:00")

    def test_json_upload(self):
        data = b'[{"case_number": "5-5", "defendants": "X", "hearing_at": "2026-10-02 09:00"}]'
        rows = parse_uploaded_file(SimpleUploadedFile("a.json", data))
        self.assertEqual(rows[0]["hearing_at"], "2026-10-02T09:00")

    def test_file_import_view(self):
        orgs = make_orgs()
        users = make_users(orgs)
        self.client.force_login(users["yurist"])
        content = "case_number,defendants,court_name\n7-7/7,Urgut tumani “Inson” ijtimoiy xizmatlar markazi,Urgut sudi\n"
        resp = self.client.post("/integratsiya/fayldan-import/", {
            "source_name": "Fayl", "file": SimpleUploadedFile("f.csv", content.encode("utf-8")),
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Case.objects.get().organization, orgs["urgut"])
        self.client.force_login(users["urgut"])
        self.assertEqual(self.client.get("/integratsiya/").status_code, 403)

