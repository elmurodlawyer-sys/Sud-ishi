"""Testlar uchun umumiy yordamchi funksiyalar."""
from accounts.models import Role, User
from cases import services
from cases.models import Case, ProceduralRole
from core.models import Classifier, ClassifierKind, Court, Organization

PASSWORD = "Sinov-Parol-2026"


def cls(kind, code):
    return Classifier.objects.get(kind=kind, code=code)


def make_orgs():
    agency = Organization.objects.create(
        full_name="O‘zbekiston Respublikasi Prezidenti huzuridagi Ijtimoiy himoya milliy agentligi",
        short_name="Ijtimoiy himoya milliy agentligi",
        org_type=cls(ClassifierKind.ORG_TYPE, "agentlik"),
        alt_names="Ижтимоий ҳимоя миллий агентлиги",
    )
    samarqand = Organization.objects.create(
        full_name="Ijtimoiy himoya milliy agentligining Samarqand viloyati boshqarmasi",
        org_type=cls(ClassifierKind.ORG_TYPE, "hududiy"), region=cls(ClassifierKind.REGION, "samarqand"), parent=agency,
        stir="301234567",
    )
    urgut = Organization.objects.create(
        full_name="Urgut tumani “Inson” ijtimoiy xizmatlar markazi",
        org_type=cls(ClassifierKind.ORG_TYPE, "inson"), region=cls(ClassifierKind.REGION, "samarqand"), parent=samarqand,
        alt_names="Ургут тумани Инсон ижтимоий хизматлар маркази",
    )
    buxoro = Organization.objects.create(
        full_name="Ijtimoiy himoya milliy agentligining Buxoro viloyati boshqarmasi",
        org_type=cls(ClassifierKind.ORG_TYPE, "hududiy"), region=cls(ClassifierKind.REGION, "buxoro"), parent=agency,
    )
    return {"agency": agency, "samarqand": samarqand, "urgut": urgut, "buxoro": buxoro}


def make_user(username, role, org=None, **kwargs):
    user = User(username=username, role=role, organization=org, email=f"{username}@example.uz", **kwargs)
    user.set_password(PASSWORD)
    user.save()
    return user


def make_users(orgs):
    return {
        "admin": make_user("admin", Role.ADMIN),
        "rahbar": make_user("rahbar", Role.RAHBARIYAT, orgs["agency"]),
        "yurist": make_user("yurist", Role.YURIDIK, orgs["agency"]),
        "samarqand": make_user("samarqand", Role.HUDUDIY, orgs["samarqand"]),
        "urgut": make_user("urgut", Role.INSON, orgs["urgut"]),
        "buxoro": make_user("buxoro", Role.HUDUDIY, orgs["buxoro"]),
    }


def make_court(name="Samarqand viloyat iqtisodiy sudi"):
    return Court.objects.create(
        name=name, court_type=cls(ClassifierKind.COURT_TYPE, "iqtisodiy"), region=cls(ClassifierKind.REGION, "samarqand")
    )


def make_case(org, user=None, number="4-1001-2601/100", court=None, role=ProceduralRole.DEFENDANT, **kwargs):
    case = Case(
        case_number=number, organization=org, role=role, court=court, plaintiffs="Karimov A.", defendants=org.full_name,
        instance=cls(ClassifierKind.INSTANCE, "birinchi"), **kwargs,
    )
    return services.register_case(case, user, notify_users=False)
