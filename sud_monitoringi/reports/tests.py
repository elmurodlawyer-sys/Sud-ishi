from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from cases.models import Case, Hearing, ProceduralRole
from core.testing import make_case, make_orgs, make_users

from .analytics import build_report
from .models import GeneratedReport, Periodicity, ReportTemplate


class ReportTests(TestCase):
    def setUp(self):
        self.orgs = make_orgs()
        self.users = make_users(self.orgs)
        self.c1 = make_case(self.orgs["urgut"], number="1-1", claim_amount=Decimal("100"))
        self.c2 = make_case(self.orgs["urgut"], number="1-2", role=ProceduralRole.PLAINTIFF, claim_amount=Decimal("50"))
        self.c3 = make_case(self.orgs["buxoro"], number="1-3", role=ProceduralRole.THIRD_PARTY)
        Hearing.objects.create(case=self.c1, scheduled_at=timezone.now() + timedelta(days=1))
        Hearing.objects.create(case=self.c1, scheduled_at=timezone.now() - timedelta(days=1), status="otkazildi")

    def test_build_report_by_org(self):
        headers, rows, totals, keys = build_report(Case.objects.valid(), ["organization"], ["total", "plaintiff", "defendant", "claim_sum", "hearings"])
        self.assertEqual(headers[0], "Tashkilot")
        by_org = {r[0]: r[1:] for r in rows}
        self.assertEqual(by_org[self.orgs["urgut"].full_name], [2, 1, 1, Decimal("150"), 2])
        self.assertEqual(by_org[self.orgs["buxoro"].full_name], [1, 0, 0, Decimal("0"), 0])
        self.assertEqual(totals, ["Jami", 3, 1, 1, Decimal("150"), 2])

    def test_combined_dims_and_period(self):
        _, rows, totals, _ = build_report(Case.objects.valid(), ["region", "role"], ["total"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(totals[-1], 3)
        _, rows, _, _ = build_report(Case.objects.valid(), ["period"], ["total"], granularity="quarter")
        self.assertIn("chorak", rows[0][0])
        _, rows, _, _ = build_report(Case.objects.valid(), ["claim_bucket"], ["total"])
        self.assertEqual(sum(r[1] for r in rows), 3)

    def test_cancelled_cases_excluded(self):
        self.c3.is_cancelled = True
        self.c3.save()
        self.client.force_login(self.users["rahbar"])
        resp = self.client.get("/hisobotlar/?dims=organization&metrics=total")
        labels = [row["dims"][0] for row in resp.context["table"]]
        self.assertEqual(labels, [self.orgs["urgut"].full_name])

    def test_views_and_exports(self):
        self.client.force_login(self.users["yurist"])
        resp = self.client.get("/hisobotlar/?dims=region&dims=role")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.client.get("/hisobotlar/?dims=region&export=xlsx").content.startswith(b"PK"))
        self.assertTrue(self.client.get("/hisobotlar/?dims=region&export=pdf").content.startswith(b"%PDF"))

    def test_scope_for_org_user(self):
        self.client.force_login(self.users["buxoro"])
        resp = self.client.get("/hisobotlar/?dims=organization")
        labels = [row["dims"][0] for row in resp.context["table"]]
        self.assertEqual(labels, [self.orgs["buxoro"].full_name])
        self.assertNotContains(resp, self.orgs["urgut"].full_name)

    def test_dashboard_counts_and_drilldown(self):
        self.client.force_login(self.users["rahbar"])
        resp = self.client.get("/")
        kpis = {k["label"]: k for k in resp.context["kpis"]}
        self.assertEqual(kpis["Jami sud ishlari"]["value"], 3)
        self.assertEqual(kpis["Agentlik tizimi — da’vogar"]["value"], 1)
        self.assertEqual(kpis["Kelgusi 7 kundagi majlislar"]["value"], 1)
        # Ko'rsatkich havolasi tarkibidagi ishlar ro'yxatini ochadi
        drill = self.client.get(kpis["Agentlik tizimi — da’vogar"]["url"])
        self.assertContains(drill, "1-2")
        self.assertNotContains(drill, ">1-1<")
        self.client.force_login(self.users["urgut"])
        kpis = {k["label"]: k for k in self.client.get("/").context["kpis"]}
        self.assertEqual(kpis["Jami sud ishlari"]["value"], 2)

    def test_save_and_periodic_generation(self):
        from django.core.management import call_command

        self.client.force_login(self.users["yurist"])
        self.client.post("/hisobotlar/saqlash/", {"dims": ["region"], "name": "Hudud", "action": "generate"})
        self.assertEqual(GeneratedReport.objects.count(), 1)
        self.client.post("/hisobotlar/saqlash/", {"dims": ["role"], "name": "Oylik", "action": "template", "periodicity": Periodicity.MONTHLY})
        template = ReportTemplate.objects.get()
        call_command("generate_reports", verbosity=0)
        call_command("generate_reports", verbosity=0)  # shu oy uchun qayta shakllantirilmaydi
        self.assertEqual(GeneratedReport.objects.filter(template=template, is_automatic=True).count(), 1)
        report = GeneratedReport.objects.filter(template=template).first()
        self.assertTrue(self.client.get(f"/hisobotlar/saqlanganlar/{report.pk}/xlsx/").status_code == 200)
        self.client.force_login(self.users["buxoro"])
        self.assertEqual(self.client.get(f"/hisobotlar/saqlanganlar/{report.pk}/xlsx/").status_code, 403)
