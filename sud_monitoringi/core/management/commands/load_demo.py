"""Sinov (demo) ma'lumotlarini yuklaydi: tashkilotlar, sudlar, foydalanuvchilar, sud ishlari.

Faqat sinov/namoyish muhiti uchun! Ishchi tizimda ishlatilmaydi.
"""
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User
from cases import services
from cases.models import (
    AgencyResult, Case, CaseEvent, CaseSource, Deadline, DeadlineKind, EventType, Hearing, HearingStatus, ProceduralRole,
    ReviewStatus, StatusCode,
)
from core.models import Classifier, ClassifierKind, Court, Organization
from core.seed import REGION_CODES
from integration.models import AdapterType, IntegrationSource
from reports.models import Periodicity, ReportTemplate

DISTRICTS = {
    "qoraqalpogiston": [("Nukus", True), ("Chimboy", False)],
    "andijon": [("Asaka", False), ("Shahrixon", False)],
    "buxoro": [("G‘ijduvon", False), ("Kogon", False)],
    "jizzax": [("Zomin", False), ("G‘allaorol", False)],
    "qashqadaryo": [("Shahrisabz", False), ("Kitob", False)],
    "navoiy": [("Karmana", False), ("Zarafshon", True)],
    "namangan": [("Chust", False), ("Pop", False)],
    "samarqand": [("Urgut", False), ("Kattaqo‘rg‘on", True)],
    "surxondaryo": [("Denov", False), ("Sherobod", False)],
    "sirdaryo": [("Guliston", True), ("Boyovut", False)],
    "toshkent-v": [("Chirchiq", True), ("Zangiota", False)],
    "fargona": [("Qo‘qon", True), ("Marg‘ilon", True)],
    "xorazm": [("Urganch", False), ("Xiva", False)],
    "toshkent-sh": [("Chilonzor", False), ("Yunusobod", False)],
}

PEOPLE = [
    "Karimov Anvar Tohirovich", "Rahimova Dilnoza Sobirovna", "Yusupov Jamshid Olimovich", "Tursunova Malika Baxtiyorovna",
    "Ergashev Bobur Nurmatovich", "Qodirova Nigora Akmalovna", "Sodiqov Farrux Ilhomovich", "Abdullayeva Zarina Rustamovna",
    "Normatov Sherzod Qahramonovich", "Xolmirzayeva Gulnora Erkinovna", "Ismoilov Doniyor Botirovich", "Mirzayeva Feruza Anvarovna",
]
COMPANIES = ["“Barakali hosil” MChJ", "“Sharq qurilish” AJ", "“Nur servis” XK", "“Oltin vodiy” MChJ", "“Yangi davr qurilish” MChJ"]
SUBJECTS = {
    "mehnat": "Ishga tiklash va majburiy progul vaqti uchun haq undirish",
    "pensiya": "Pensiya miqdorini qayta hisoblash to‘g‘risida",
    "nafaqa": "Ijtimoiy nafaqa tayinlashni rad etish to‘g‘risidagi qarorni bekor qilish",
    "nogironlik": "Nogironlik guruhini belgilash bo‘yicha xulosani haqiqiy emas deb topish",
    "undirish": "Ortiqcha to‘langan nafaqa summasini undirish",
    "shartnoma": "Shartnoma majburiyatlarini bajarmaganlik uchun penya undirish",
    "mulk": "Mol-mulkni qaytarish to‘g‘risida",
    "mamuriy_hujjat": "Ma’muriy hujjatni haqiqiy emas deb topish",
    "vasiylik": "Vasiylik belgilash to‘g‘risida",
    "boshqa": "Boshqa talablar",
}


class Command(BaseCommand):
    help = "Sinov uchun namuna ma'lumotlarni yuklaydi (tashkilotlar, foydalanuvchilar, sud ishlari)."

    def add_arguments(self, parser):
        parser.add_argument("--cases", type=int, default=120)
        parser.add_argument("--password", default="Demo2026!", help="Demo foydalanuvchilar paroli")
        parser.add_argument("--seed", type=int, default=2026)
        parser.add_argument("--force", action="store_true", help="Sud ishlari mavjud bo'lsa ham qo'shish")

    def c(self, kind, code):
        return Classifier.objects.get(kind=kind, code=code)

    @transaction.atomic
    def handle(self, *args, **opts):
        if Case.objects.exists() and not opts["force"]:
            raise CommandError("Bazada sud ishlari mavjud. Qo‘shimcha demo ma’lumot uchun --force qo‘shing.")
        rnd = random.Random(opts["seed"])
        orgs = self.load_organizations()
        courts = self.load_courts()
        users = self.load_users(orgs, opts["password"])
        self.load_cases(rnd, orgs, courts, users, opts["cases"])
        self.load_integration()
        ReportTemplate.objects.get_or_create(
            name="Oylik hisobot: hududlar va protsessual maqom kesimida",
            defaults={"params": {"dims": ["region", "role"], "metrics": ["total", "open", "closed", "claim_sum", "hearings"]},
                      "periodicity": Periodicity.MONTHLY, "created_by": users["yurist"]},
        )
        self.stdout.write(self.style.SUCCESS("Demo ma’lumotlar yuklandi."))
        self.stdout.write("Foydalanuvchilar (parol: %s):" % opts["password"])
        for key, user in users.items():
            self.stdout.write(f"  {user.username:<12} — {user.get_role_display()}{' / ' + str(user.organization) if user.organization else ''}")

    def load_organizations(self):
        agency_type, reg_type = self.c(ClassifierKind.ORG_TYPE, "agentlik"), self.c(ClassifierKind.ORG_TYPE, "hududiy")
        inson_type, other_type = self.c(ClassifierKind.ORG_TYPE, "inson"), self.c(ClassifierKind.ORG_TYPE, "muassasa")
        agency, _ = Organization.objects.get_or_create(
            full_name="O‘zbekiston Respublikasi Prezidenti huzuridagi Ijtimoiy himoya milliy agentligi",
            defaults={
                "short_name": "Ijtimoiy himoya milliy agentligi", "org_type": agency_type,
                "region": self.c(ClassifierKind.REGION, "respublika"),
                "alt_names": "Ижтимоий ҳимоя миллий агентлиги\nНациональное агентство социальной защиты\nIjtimoiy himoya agentligi",
            },
        )
        result = {"agency": agency, "regional": {}, "inson": [], "other": []}
        for code in REGION_CODES:
            region = self.c(ClassifierKind.REGION, code)
            short = region.name.replace(" viloyati", " viloyati").replace(" shahri", " shahar")
            reg, _ = Organization.objects.get_or_create(
                full_name=f"Ijtimoiy himoya milliy agentligining {short} boshqarmasi",
                defaults={
                    "short_name": f"{short} ijtimoiy himoya boshqarmasi", "org_type": reg_type, "region": region, "parent": agency,
                    "alt_names": f"Ijtimoiy himoya milliy agentligi {short} boshqarmasi\n{short} boshqarmasi (Ijtimoiy himoya)",
                },
            )
            result["regional"][code] = reg
            for district, is_city in DISTRICTS[code]:
                unit = "shahar" if is_city else "tumani"
                center, _ = Organization.objects.get_or_create(
                    full_name=f"{district} {unit} “Inson” ijtimoiy xizmatlar markazi",
                    defaults={
                        "short_name": f"{district} {unit} “Inson” markazi", "org_type": inson_type, "region": region,
                        "district": f"{district} {unit}", "parent": reg,
                        "alt_names": f"{district} {unit} Inson ijtimoiy xizmatlar markazi\n{district} {unit} Inson markazi",
                    },
                )
                result["inson"].append(center)
        for name, alt in [
            ("Nogironligi bo‘lgan shaxslarni reabilitatsiya qilish va protezlash respublika markazi", "Respublika reabilitatsiya va protezlash markazi"),
            ("“Saxovat” keksalar va nogironligi bo‘lgan shaxslar pansionati (Toshkent shahri)", "Saxovat pansionati Toshkent"),
        ]:
            org, _ = Organization.objects.get_or_create(
                full_name=name, defaults={"org_type": other_type, "region": self.c(ClassifierKind.REGION, "toshkent-sh"),
                                          "parent": agency, "alt_names": alt},
            )
            result["other"].append(org)
        return result

    def load_courts(self):
        courts = []
        types = [("fuqarolik", "Fuqarolik ishlari bo‘yicha {d} tumanlararo sudi"), ("iqtisodiy", "{r} iqtisodiy sudi"),
                 ("mamuriy", "{r} ma’muriy sudi")]
        for code in REGION_CODES:
            region = self.c(ClassifierKind.REGION, code)
            rname = region.name.replace(" viloyati", " viloyat").replace(" shahri", " shahar")
            for type_code, pattern in types:
                name = pattern.format(r=rname, d=DISTRICTS[code][0][0])
                court = Court.objects.filter(name=name).first() or Court.objects.create(
                    name=name, court_type=self.c(ClassifierKind.COURT_TYPE, type_code), region=region
                )
                courts.append(court)
        Court.objects.filter(name="O‘zbekiston Respublikasi Oliy sudi").exists() or Court.objects.create(
            name="O‘zbekiston Respublikasi Oliy sudi", court_type=self.c(ClassifierKind.COURT_TYPE, "oliy"),
            region=self.c(ClassifierKind.REGION, "respublika"),
        )
        return courts

    def load_users(self, orgs, password):
        specs = [
            ("admin", Role.ADMIN, None, "Administrator", "Tizim", True),
            ("rahbar", Role.RAHBARIYAT, orgs["agency"], "Rahbariyat", "Agentlik", False),
            ("yurist", Role.YURIDIK, orgs["agency"], "Yuridik", "Bo‘lim", False),
            ("itmarkaz", Role.AT_MARKAZ, orgs["agency"], "AT markazi", "Xodim", False),
            ("samarqand", Role.HUDUDIY, orgs["regional"]["samarqand"], "Samarqand", "Boshqarma", False),
            ("urgut", Role.INSON, next(o for o in orgs["inson"] if o.full_name.startswith("Urgut")), "Urgut", "Inson markazi", False),
            ("reabilitatsiya", Role.TASHKILOT, orgs["other"][0], "Reabilitatsiya", "Markazi", False),
        ]
        users = {}
        for username, role, org, last, first, superuser in specs:
            user = User.objects.filter(username=username).first()
            if user is None:
                user = User(username=username, role=role, organization=org, last_name=last, first_name=first,
                            is_superuser=superuser, is_staff=superuser, email=f"{username}@example.uz")
                user.set_password(password)
                user.save()
            users[username] = user
        return users

    def load_cases(self, rnd, orgs, courts, users, count):
        now = timezone.now()
        today = timezone.localdate()
        categories = list(Classifier.objects.filter(kind=ClassifierKind.CASE_CATEGORY, code__in=SUBJECTS.keys()))
        outcomes = list(Classifier.objects.filter(kind=ClassifierKind.OUTCOME).exclude(code="boshqa"))
        instances = {c.code: c for c in Classifier.objects.filter(kind=ClassifierKind.INSTANCE)}
        hearing_results = {c.code: c for c in Classifier.objects.filter(kind=ClassifierKind.HEARING_RESULT)}
        doc_type = self.c(ClassifierKind.DEADLINE_TYPE, "yozma_fikr")
        appeal_type = self.c(ClassifierKind.DEADLINE_TYPE, "apellyatsiya")
        pool = orgs["inson"] * 3 + list(orgs["regional"].values()) * 2 + orgs["other"] + [orgs["agency"]] * 3
        org_users = {}
        for u in users.values():
            if u.organization_id:
                org_users.setdefault(u.organization_id, []).append(u)
        statuses = [StatusCode.NEW, StatusCode.IN_PROGRESS, StatusCode.HEARING_SET, StatusCode.HEARING_SET,
                    StatusCode.HEARING_POSTPONED, StatusCode.ACT_ADOPTED, StatusCode.APPEAL, StatusCode.CASSATION,
                    StatusCode.FINISHED, StatusCode.FINISHED, StatusCode.FINISHED, StatusCode.ARCHIVED, StatusCode.CLARIFYING]
        for i in range(count):
            org = rnd.choice(pool)
            region_courts = [c for c in courts if c.region_id == org.region_id] or courts
            court = rnd.choice(region_courts)
            category = rnd.choice(categories)
            role = rnd.choices([ProceduralRole.DEFENDANT, ProceduralRole.PLAINTIFF, ProceduralRole.THIRD_PARTY], [55, 30, 15])[0]
            person = rnd.choice(PEOPLE + COMPANIES)
            plaintiffs, defendants, third = person, org.full_name, ""
            if role == ProceduralRole.PLAINTIFF:
                plaintiffs, defendants = org.full_name, person
            elif role == ProceduralRole.THIRD_PARTY:
                plaintiffs, defendants, third = person, rnd.choice(COMPANIES), org.full_name
            created = now - timedelta(days=rnd.randint(0, 360), hours=rnd.randint(0, 10))
            status_code = rnd.choice(statuses)
            prefix = {"fuqarolik": "2", "iqtisodiy": "4", "mamuriy": "3"}.get(court.court_type.code, "2")
            case = Case(
                case_number=f"{prefix}-{1000 + court.pk}-{created:%y}01/{rnd.randint(10, 99)}{i:03d}",
                organization=org, role=role, plaintiffs=plaintiffs, defendants=defendants, third_parties=third,
                court=court, instance=instances["birinchi"], category=category, subject=SUBJECTS.get(category.code, ""),
                claim_amount=Decimal(rnd.choice([0, 0, 1, 5, 12, 25, 60, 150, 480, 1200])) * Decimal(rnd.randint(900_000, 1_100_000)) or None,
                judge=rnd.choice(["A. Xolmatov", "S. Nazarova", "D. Ismoilov", "M. Rasulova", "B. Qurbonov"]),
                filed_date=(created - timedelta(days=rnd.randint(3, 30))).date(),
                responsible=rnd.choice(org_users.get(org.pk, [None]) + [None]) or (users["yurist"] if org == orgs["agency"] else None),
                source=rnd.choice([CaseSource.MANUAL, CaseSource.INTEGRATION]),
                created_at=created, last_activity_at=created,
                review_status=rnd.choice([ReviewStatus.APPROVED, ReviewStatus.APPROVED, ReviewStatus.DRAFT, ReviewStatus.PENDING, ReviewStatus.RETURNED]),
            )
            if case.source == CaseSource.INTEGRATION:
                case.source_name, case.source_fetched_at, case.source_updated_at = "jadval2.sud.uz", created, created
            if case.review_status == ReviewStatus.RETURNED:
                case.review_comment = "Da’vo summasi va mas’ul xodim ma’lumotlarini aniqlashtiring."
            case.status = services.status_by_code(StatusCode.NEW)
            services.register_case(case, users["yurist"] if case.source == CaseSource.MANUAL else None, notify_users=False)
            CaseEvent.objects.filter(case=case).update(created_at=created)

            # Sud majlislari tarixi
            n_hearings = rnd.randint(0, 3)
            for k in range(n_hearings):
                at = timezone.make_aware(datetime.combine(created.date() + timedelta(days=15 + 20 * k), time(rnd.choice([9, 10, 11, 14, 15]), rnd.choice([0, 30]))))
                past = at < now
                Hearing.objects.create(
                    case=case, scheduled_at=at, location=f"{rnd.randint(1, 12)}-zal", responsible=case.responsible,
                    status=HearingStatus.HELD if past else HearingStatus.SCHEDULED,
                    result=hearing_results["otkazildi"] if past else None, source=case.source,
                )
            final = status_code in (StatusCode.FINISHED, StatusCode.ARCHIVED)
            if status_code in (StatusCode.HEARING_SET, StatusCode.HEARING_POSTPONED) or (not final and rnd.random() < 0.5):
                at = timezone.make_aware(datetime.combine(today + timedelta(days=rnd.randint(0, 21)), time(rnd.choice([9, 10, 14, 15]), 0)))
                Hearing.objects.create(case=case, scheduled_at=at, location=f"{rnd.randint(1, 12)}-zal",
                                       responsible=case.responsible, status=HearingStatus.SCHEDULED, source=case.source)
            if status_code in (StatusCode.APPEAL, StatusCode.CASSATION):
                case.instance = instances["apellyatsiya" if status_code == StatusCode.APPEAL else "kassatsiya"]
                case.save()
                services.ensure_stage(case, None, "Demo: yuqori instansiyaga o‘tdi")
            if final:
                case.outcome = rnd.choice(outcomes)
                case.outcome_date = min(today, (created + timedelta(days=rnd.randint(20, 120))).date())
                case.agency_result = rnd.choices(
                    [AgencyResult.FAVOR, AgencyResult.AGAINST, AgencyResult.PARTIAL, AgencyResult.NEUTRAL], [55, 20, 15, 10])[0]
                if case.claim_amount and case.agency_result in (AgencyResult.AGAINST, AgencyResult.PARTIAL):
                    case.awarded_amount = (case.claim_amount * Decimal(rnd.choice([30, 50, 100])) / 100).quantize(Decimal("1"))
                if rnd.random() < 0.15:
                    case.outcome = None
            case.status = services.status_by_code(status_code)
            case.save()
            services.record_event(case, None, EventType.STATUS, f"Ish holati: Yangi aniqlangan → {case.status}", comment="Demo ma’lumot")
            case.refresh_next_hearing()

            # Nazorat muddatlari
            if not final and rnd.random() < 0.6:
                due = today + timedelta(days=rnd.randint(-10, 20))
                Deadline.objects.create(case=case, kind=DeadlineKind.PROCEDURAL, deadline_type=doc_type,
                                        title="Sudga yozma fikr (e’tiroz) taqdim etish", due_date=due, responsible=case.responsible)
            if status_code == StatusCode.ACT_ADOPTED:
                Deadline.objects.create(case=case, kind=DeadlineKind.PROCEDURAL, deadline_type=appeal_type,
                                        title="Apellyatsiya shikoyati berish masalasini hal etish",
                                        due_date=today + timedelta(days=rnd.randint(-3, 25)), responsible=case.responsible)
            # Faollik sanasi: ba'zi ishlar uzoq muddat yangilanmagan bo'lib qolsin
            last = created + timedelta(days=rnd.randint(0, 60))
            Case.objects.filter(pk=case.pk).update(last_activity_at=min(last, now))

    def load_integration(self):
        IntegrationSource.objects.get_or_create(
            name="Demo manba (sinov uchun)",
            defaults={"adapter": AdapterType.DEMO, "interval_minutes": 60, "is_active": True, "config": {"count": 15}},
        )
        IntegrationSource.objects.get_or_create(
            name="jadval2.sud.uz (sud majlislari jadvali)",
            defaults={
                "adapter": AdapterType.HTML, "base_url": "https://jadval2.sud.uz/", "interval_minutes": 360, "is_active": False,
                "config": {
                    "pages": [{"url": "https://jadval2.sud.uz/", "court_name": ""}],
                    "date_format": "%d.%m.%Y", "days_back": 0, "days_forward": 14,
                    "_izoh": "Haqiqiy sahifa manzillari va sud nomlarini kiriting, so‘ng manbani faollashtiring.",
                },
            },
        )
