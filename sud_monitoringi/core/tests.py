import io

from django.test import TestCase
from openpyxl import Workbook

from .importers import import_organizations
from .models import Classifier, ClassifierKind, Organization
from .normalize import contains_phrase, normalize_case_number, normalize_name
from .testing import make_orgs


class NormalizeTests(TestCase):
    def test_apostrophes_quotes_and_case(self):
        self.assertEqual(normalize_name("Farg‘ona"), normalize_name("Farg'ona"))
        self.assertEqual(normalize_name("FARGʻONA"), normalize_name("fargona"))
        self.assertEqual(normalize_name("“Inson” markazi"), normalize_name('"Inson" markazi'))

    def test_cyrillic_and_h_x(self):
        self.assertEqual(normalize_name("Ижтимоий ҳимоя"), normalize_name("Ijtimoiy ximoya"))
        self.assertEqual(normalize_name("Ijtimoiy himoya"), normalize_name("Ijtimoiy ximoya"))
        # sh / ch saqlanadi
        self.assertEqual(normalize_name("Shahrisabz"), "shaxrisabz")

    def test_contains_phrase_whole_words(self):
        self.assertTrue(contains_phrase("urgut tumani inson markazi", "inson markazi"))
        self.assertFalse(contains_phrase("insonparvarlik markazi", "inson markazi"))

    def test_case_number(self):
        self.assertEqual(normalize_case_number(" 4-1001–2601 / 100 "), "4-1001-2601/100")


class ClassifierSeedTests(TestCase):
    def test_required_classifiers_seeded(self):
        statuses = set(Classifier.objects.filter(kind=ClassifierKind.CASE_STATUS).values_list("code", flat=True))
        self.assertEqual(len(statuses), 11)
        self.assertTrue({"yangi", "yakunlangan", "arxivlangan"} <= statuses)
        self.assertEqual(Classifier.objects.filter(kind=ClassifierKind.REGION).count(), 15)
        self.assertTrue(Classifier.objects.get(kind=ClassifierKind.CASE_STATUS, code="yakunlangan").is_final)


class OrganizationTests(TestCase):
    def setUp(self):
        self.orgs = make_orgs()

    def test_match_keys_include_all_names(self):
        keys = self.orgs["urgut"].match_keys.splitlines()
        self.assertIn(normalize_name("Urgut tumani “Inson” ijtimoiy xizmatlar markazi"), keys)
        self.assertIn(normalize_name("Ургут тумани Инсон ижтимоий хизматлар маркази"), keys)

    def test_descendants(self):
        ids = self.orgs["agency"].descendant_ids()
        self.assertEqual(set(ids), {o.pk for o in self.orgs.values()})
        self.assertEqual(set(self.orgs["samarqand"].descendant_ids()), {self.orgs["samarqand"].pk, self.orgs["urgut"].pk})

    def test_excel_import_creates_and_updates(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["full_name", "short_name", "stir", "org_type", "region", "district", "parent", "previous_names", "alt_names", "is_active"])
        ws.append(["Kattaqo‘rg‘on shahar “Inson” markazi", "", "", "inson", "Samarqand viloyati", "", "301234567", "Eski nom", "Muqobil 1; Muqobil 2", "ha"])
        ws.append(["Ijtimoiy himoya milliy agentligining Samarqand viloyati boshqarmasi (yangi)", "", "301234567", "hududiy", "samarqand", "", "", "", "", ""])
        ws.append(["Noto‘g‘ri turdagi tashkilot", "", "", "mavjud-emas", "", "", "", "", "", ""])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        result = import_organizations(buf)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(len(result["errors"]), 1)
        new = Organization.objects.get(full_name__startswith="Kattaqo")
        self.assertEqual(new.parent, self.orgs["samarqand"])
        self.assertEqual(new.alt_names, "Muqobil 1\nMuqobil 2")
        self.orgs["samarqand"].refresh_from_db()
        self.assertTrue(self.orgs["samarqand"].full_name.endswith("(yangi)"))
