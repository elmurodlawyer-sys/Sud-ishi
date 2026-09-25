"""Boshlang'ich klassifikatorlar. Keyinchalik tizim ichidan tahrirlanadi.

(kod, nomi, is_system, is_final)
"""

REGIONS = [
    "Qoraqalpog‘iston Respublikasi", "Andijon viloyati", "Buxoro viloyati", "Jizzax viloyati",
    "Qashqadaryo viloyati", "Navoiy viloyati", "Namangan viloyati", "Samarqand viloyati",
    "Surxondaryo viloyati", "Sirdaryo viloyati", "Toshkent viloyati", "Farg‘ona viloyati",
    "Xorazm viloyati", "Toshkent shahri",
]
REGION_CODES = [
    "qoraqalpogiston", "andijon", "buxoro", "jizzax", "qashqadaryo", "navoiy", "namangan", "samarqand",
    "surxondaryo", "sirdaryo", "toshkent-v", "fargona", "xorazm", "toshkent-sh",
]

DATA = {
    "region": [(code, name, True, False) for code, name in zip(REGION_CODES, REGIONS)]
    + [("respublika", "Respublika (markaziy)", True, False)],
    "org_type": [
        ("agentlik", "Agentlik (markaziy apparat)", True, False),
        ("hududiy", "Agentlikning hududiy boshqarmasi", True, False),
        ("inson", "“Inson” ijtimoiy xizmatlar markazi", True, False),
        ("muassasa", "Agentlik tizimidagi boshqa tashkilot (muassasa)", True, False),
    ],
    "court_type": [
        ("fuqarolik", "Fuqarolik ishlari bo‘yicha sud", False, False),
        ("iqtisodiy", "Iqtisodiy sud", False, False),
        ("mamuriy", "Ma’muriy sud", False, False),
        ("jinoyat", "Jinoyat ishlari bo‘yicha sud", False, False),
        ("viloyat", "Viloyat va unga tenglashtirilgan sud", False, False),
        ("oliy", "O‘zbekiston Respublikasi Oliy sudi", False, False),
    ],
    "instance": [
        ("birinchi", "Birinchi instansiya", True, False),
        ("apellyatsiya", "Apellyatsiya instansiyasi", True, False),
        ("kassatsiya", "Kassatsiya instansiyasi", True, False),
        ("taftish", "Taftish tartibida qayta ko‘rish", True, False),
        ("boshqa", "Yangi ochilgan holatlar bo‘yicha qayta ko‘rish", True, False),
    ],
    "case_category": [
        ("mehnat", "Mehnat nizolari", False, False),
        ("pensiya", "Pensiya ta’minoti bilan bog‘liq nizolar", False, False),
        ("nafaqa", "Ijtimoiy nafaqa va moddiy yordam bo‘yicha nizolar", False, False),
        ("nogironlik", "Nogironlik va reabilitatsiya bilan bog‘liq nizolar", False, False),
        ("undirish", "Pul mablag‘larini undirish", False, False),
        ("shartnoma", "Shartnoma majburiyatlari bo‘yicha nizolar", False, False),
        ("mulk", "Mulkiy nizolar", False, False),
        ("mamuriy_hujjat", "Ma’muriy hujjat ustidan shikoyat (nizo)", False, False),
        ("vasiylik", "Vasiylik va homiylik ishlari", False, False),
        ("mamuriy_huquqbuzarlik", "Ma’muriy huquqbuzarlik ishlari", False, False),
        ("jinoyat", "Jinoyat ishlari", False, False),
        ("boshqa", "Boshqa ishlar", False, False),
    ],
    "case_status": [
        ("yangi", "Yangi aniqlangan", True, False),
        ("aniqlashtirilmoqda", "Ma’lumotlari aniqlashtirilmoqda", True, False),
        ("korilmoqda", "Ko‘rib chiqilmoqda", True, False),
        ("majlis_tayinlangan", "Sud majlisi tayinlangan", True, False),
        ("majlis_qoldirilgan", "Sud majlisi qoldirilgan", True, False),
        ("hujjat_qabul_qilingan", "Sud hujjati qabul qilingan", True, False),
        ("apellyatsiya", "Apellyatsiya bosqichida", True, False),
        ("kassatsiya", "Kassatsiya bosqichida", True, False),
        ("qayta_korish", "Boshqa qayta ko‘rib chiqish bosqichida", True, False),
        ("yakunlangan", "Yakunlangan", True, True),
        ("arxivlangan", "Arxivlangan", True, True),
    ],
    "outcome": [
        ("toliq_qanoatlantirildi", "Da’vo (ariza) to‘liq qanoatlantirildi", False, False),
        ("qisman_qanoatlantirildi", "Da’vo (ariza) qisman qanoatlantirildi", False, False),
        ("rad_etildi", "Da’vo (ariza) rad etildi", False, False),
        ("tugatildi", "Ish yuritish tugatildi", False, False),
        ("korilmasdan", "Da’vo ko‘rmasdan qoldirildi", False, False),
        ("kelishuv", "Kelishuv bitimi tasdiqlandi", False, False),
        ("qaytarildi", "Da’vo arizasi qaytarildi", False, False),
        ("ozgarishsiz", "Sud hujjati o‘zgarishsiz qoldirildi", False, False),
        ("bekor_qilindi", "Sud hujjati bekor qilindi", False, False),
        ("ozgartirildi", "Sud hujjati o‘zgartirildi", False, False),
        ("boshqa", "Boshqa natija", False, False),
    ],
    "document_type": [
        ("davo_arizasi", "Da’vo arizasi yoki ariza", True, False),
        ("ajrim_chaqiruv", "Sud ajrimi va chaqiruvi", False, False),
        ("yozma_fikr", "Yozma fikr, e’tiroz va iltimosnomalar", False, False),
        ("dalillar", "Dalillar", False, False),
        ("yakuniy_hujjat", "Sud hal qiluv qarori yoki boshqa yakuniy sud hujjati", True, False),
        ("shikoyat", "Apellyatsiya va kassatsiya shikoyatlari", False, False),
        ("boshqa", "Boshqa protsessual hujjatlar", False, False),
    ],
    "hearing_result": [
        ("otkazildi", "Majlis o‘tkazildi, ish ko‘rish davom etadi", False, False),
        ("qoldirildi", "Majlis qoldirildi", False, False),
        ("tanaffus", "Tanaffus e’lon qilindi", False, False),
        ("hujjat_qabul", "Sud hujjati qabul qilindi", False, False),
        ("toxtatildi", "Ish yuritish to‘xtatildi", False, False),
        ("otkazilmadi", "Majlis o‘tkazilmadi", False, False),
    ],
    "deadline_type": [
        ("yozma_fikr", "Yozma fikr (e’tiroz) taqdim etish", False, False),
        ("dalil", "Dalillar taqdim etish", False, False),
        ("apellyatsiya", "Apellyatsiya shikoyati berish", False, False),
        ("kassatsiya", "Kassatsiya shikoyati berish", False, False),
        ("ijro", "Sud hujjatini ijro etish", False, False),
        ("hisobot", "Rahbariyatga axborot berish", False, False),
        ("boshqa", "Boshqa", False, False),
    ],
}


def seed_classifiers(Classifier):
    """Mavjud yozuvlarni o'zgartirmasdan yetishmaydiganlarini qo'shadi."""
    created = 0
    for kind, rows in DATA.items():
        for order, (code, name, is_system, is_final) in enumerate(rows, start=1):
            _, was_created = Classifier.objects.get_or_create(
                kind=kind,
                code=code,
                defaults={"name": name, "order": order * 10, "is_system": is_system, "is_final": is_final},
            )
            created += int(was_created)
    return created
