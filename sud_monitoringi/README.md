# “Sud monitoringi” axborot tizimi

O‘zbekiston Respublikasi Prezidenti huzuridagi Ijtimoiy himoya milliy agentligi va uning tizimidagi tashkilotlar
ishtirokidagi sud ishlarini markazlashgan tartibda hisobga olish va monitoring qilish tizimi.
Texnik talab (TT) asosida ishlab chiqilgan mustaqil veb-ilova.

- **Texnologiya:** Python 3.11+, Django 5.2, PostgreSQL (ishchi muhit) yoki SQLite (sinov), Bootstrap 5, Chart.js
- **Interfeys:** o‘zbek tilida, lotin yozuvida; kompyuter, planshet va telefon ekranlariga moslashgan
- **Tashqi kutubxonalar internetdan yuklanmaydi** — barcha CSS/JS/shriftlar `static/` ichida

---

## 1. Tezkor ishga tushirish (sinov rejimi, SQLite)

```bash
cd sud_monitoringi
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

export DEBUG=1                      # Windows: set DEBUG=1
python manage.py migrate            # jadvallar va boshlang‘ich klassifikatorlar
python manage.py load_demo          # namuna ma’lumotlar (ixtiyoriy)
python manage.py runserver
```

Brauzerda: <http://127.0.0.1:8000>. Demo foydalanuvchilar (parol: `Demo2026!`):

| Login | Rol |
|---|---|
| `admin` | Tizim administratori |
| `rahbar` | Agentlik rahbariyati |
| `yurist` | Agentlik Yuridik bo‘limi xodimi |
| `itmarkaz` | Axborot texnologiyalari markazi xodimi |
| `samarqand` | Samarqand viloyati hududiy boshqarmasi |
| `urgut` | Urgut tumani “Inson” ijtimoiy xizmatlar markazi |
| `reabilitatsiya` | Tizimdagi boshqa tashkilot |

> `load_demo` faqat sinov uchun. Ishchi tizimda uni ishlatmang: administratorni
> `python manage.py createsuperuser` bilan yarating va unga “Tizim administratori” rolini bering.

Testlar: `DEBUG=1 python manage.py test` (62 ta test).

## 2. Ishchi muhitga o‘rnatish

### Docker bilan (tavsiya etiladi)

```bash
cp .env.example .env       # SECRET_KEY, ALLOWED_HOSTS, DB_PASSWORD va boshqalarni to‘ldiring
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

`docker-compose.yml` uchta xizmatni ko‘taradi: `db` (PostgreSQL 16), `web` (gunicorn) va `scheduler`
(integratsiya, eslatmalar, davriy hisobotlar va kunlik zaxira nusxa).
HTTPS uchun oldiga nginx (yoki boshqa reverse-proxy) qo‘ying va `.env` da `BEHIND_PROXY=1` qiling.

### Dockersiz

1. PostgreSQL bazasi va foydalanuvchisini yarating, `.env.example` asosida `.env` tuzing (`DB_ENGINE=postgres`).
2. `pip install -r requirements.txt`, `python manage.py migrate`, `python manage.py collectstatic`.
3. `gunicorn config.wsgi:application --bind 127.0.0.1:8000` ni systemd xizmati sifatida ishga tushiring.
4. Fon vazifalari uchun `python manage.py run_scheduler` ni alohida xizmat qiling **yoki** cron'dan foydalaning:

```cron
*/5 * * * *  cd /opt/sud_monitoringi && .venv/bin/python manage.py run_integration
0 * * * *    cd /opt/sud_monitoringi && .venv/bin/python manage.py send_reminders
15 * * * *   cd /opt/sud_monitoringi && .venv/bin/python manage.py generate_reports
0 2 * * *    cd /opt/sud_monitoringi && .venv/bin/python manage.py backup --keep 30
```

Barcha sozlamalar muhit o‘zgaruvchilari orqali beriladi — ro‘yxat va izohlar `.env.example` faylida.

## 3. Foydalanuvchi rollari va huquqlar

| Rol | Ko‘rish doirasi | Imkoniyatlar |
|---|---|---|
| Agentlik rahbariyati | barcha tashkilotlar | dashboard, ro‘yxatlar, hisobotlar, eksport (tahrirlashsiz) |
| Yuridik bo‘lim | barcha tashkilotlar | kiritish, tahrirlash, **tasdiqlash, qaytarish, arxivga olish, bekor qilish**, ma’lumotnomalar, integratsiya |
| Hududiy boshqarma | o‘z boshqarmasi va unga bo‘ysunuvchi tashkilotlar | kiritish, tahrirlash, hujjat biriktirish, tasdiqqa yuborish |
| “Inson” markazi / boshqa tashkilot | o‘z tashkiloti (va quyi tashkilotlari) | kiritish, tahrirlash, hujjat biriktirish, tasdiqqa yuborish |
| AT markazi | barcha tashkilotlar (ko‘rish) | integratsiyani boshqarish, harakatlar jurnali |
| Tizim administratori | hammasi | foydalanuvchilar, zaxira nusxalar, jurnal, barcha ma’lumotnomalar |

Oddiy foydalanuvchi sud ishini o‘chira olmaydi. Noto‘g‘ri yoki takroriy yozuvni Yuridik bo‘lim sabab ko‘rsatgan holda
**bekor qiladi** yoki **arxivga oladi** — yozuv tarix bilan saqlanib qoladi.

## 4. jadval2.sud.uz bilan integratsiya

“Integratsiya” bo‘limida manbalar sozlanadi. Har bir manba belgilangan davriylikda avtomatik tekshiriladi:

1. manbadan yozuvlar olinadi va yagona ko‘rinishga keltiriladi;
2. da’vogar, javobgar va uchinchi shaxslar matnidan Agentlik tizimidagi tashkilotlar aniqlanadi —
   to‘liq, qisqa, **oldingi** va **muqobil** nomlari hamda STIR bo‘yicha. Kirill/lotin yozuvi, tutuq belgilari
   (‘ ’ ' ʻ), qo‘shtirnoqlar va “h/x” farqlari hisobga olinmaydi;
3. yozuv oldingi tekshiruv natijasi bilan solishtiriladi (xesh). O‘zgarmagan bo‘lsa, hech narsa qilinmaydi;
4. yangi ish uchun elektron kartochka yaratiladi, tegishli tashkilot, uning yuqori tashkiloti va
   Yuridik bo‘limga xabarnoma yuboriladi;
5. mavjud ish **qayta kartochka yaratilmasdan** yangilanadi: o‘zgarishlar maydonlar kesimida tarixga yoziladi,
   sud majlisi sanasi o‘zgarsa, majlis ko‘chiriladi va xabar beriladi;
6. tashqi manba ishlamasa, xato seans jurnaliga yoziladi — tizimning qolgan qismi ishlashda davom etadi.

Ulanish usullari:

| Usul | Qachon ishlatiladi |
|---|---|
| **Rasmiy API (JSON)** | Oliy sud rasmiy API/veb-servis taqdim etganda (TT 3.2 — birinchi navbatdagi usul) |
| **Veb-sahifa jadvali (HTML)** | API bo‘lmaganda: jadval2.sud.uz sahifalaridagi jadvallar o‘qiladi. Ustunlar (Ish raqami, Da’vogar, Javobgar, Sudya, Vaqti...) lotin, kirill va rus tilidagi sarlavhalar bo‘yicha avtomatik aniqlanadi |
| **Fayldan import** | JSON/CSV/XLSX fayl orqali (masalan, manbadan qo‘lda olingan ro‘yxat) |
| **Demo** | Sinov uchun soxta ma’lumotlar |

> **Muhim.** Ishlab chiqish muhitidan jadval2.sud.uz saytiga ulanish imkoni bo‘lmadi, shu sababli
> sahifa tuzilishi yoki rasmiy API maydonlari oldindan ma’lum emas. Adapterlar moslashuvchan qilib yozilgan:
> haqiqiy manzillar, maydonlar moslamasi (`field_map`) va sarlavhalar (`header_map`) kod o‘zgartirilmasdan,
> manba sozlamalarida (JSON) beriladi. Sozlash namunalari manba tahrirlash sahifasida ko‘rsatilgan.
> Rasmiy API kelishilgach, `field_map` ni API javobiga moslash kifoya.

Yagona yozuv maydonlari: `external_key, case_number, court_name, court_type, region, instance, category,
plaintiffs, defendants, third_parties, judge, hearing_at, location, subject, claim_amount, url`.

Qo‘lda ishga tushirish: `python manage.py run_integration --all` yoki `--source <ID>`.

## 5. Modullar va TT bandlariga muvofiqlik

| TT bandi | Amalga oshirilishi |
|---|---|
| 3.1 Tashkilotlar ma’lumotnomasi | “Ma’lumotnomalar → Tashkilotlar”: to‘liq/qisqa/oldingi/muqobil nomlar, STIR, turi, hududi, yuqori tashkiloti, faolligi; Excel’dan import va eksport |
| 3.2 Avtomatik aniqlash | `integration/` — adapterlar, nom moslash, o‘zgarishlarni aniqlash, takroriy kartochkaga yo‘l qo‘ymaslik |
| 3.3 Elektron kartochka | TT’dagi barcha maydonlar; tizimdagi yagona raqam `SM-YYYY-NNNNNN`; ma’lumot manbasi va yangilangan sanalar |
| 3.4 Holat va bosqichlar | 11 ta holat klassifikatori; birinchi instansiya → apellyatsiya → kassatsiya → qayta ko‘rish bosqichlari; o‘zgarishda sana, foydalanuvchi va **majburiy izoh** qayd etiladi |
| 3.5 Majlislar va muddatlar | majlislar tarixi, mas’ul xodim, natija, keyingi majlis; protsessual va ichki nazorat muddatlari; “Nazorat” sahifasi |
| 3.6 Hujjatlar | 7 turdagi hujjat; turi, sanasi, raqami, yuklagan foydalanuvchi va vaqt saqlanadi; yuklab olish huquq tekshiruvi bilan |
| 3.7 Qidiruv va filtr | TT’dagi 18 mezon + qo‘shimcha (nazorat, tasdiqlash holati, summa oralig‘i), kombinatsiyalangan |
| 3.8 Avtomatik hisobotlar | 15 ta kesim (1–3 tasini birga tanlash mumkin), 12 ko‘rsatkich; Excel, PDF va chop etish |
| 3.9 Dashboard | 12 ko‘rsatkich va 7 diagramma; har biri bosilganda tegishli ishlar ro‘yxati ochiladi |
| 4 Biznes qoidalar | bitta ish — bitta kartochka (bazada ham cheklov bor); jismonan o‘chirish yo‘q; bekor qilish/arxiv sabab bilan; yakunlanganda natija majburiy; muddati o‘tgan va yangilanmagan ishlar nazoratda |
| 5 Xabarnomalar | 10 holat bo‘yicha tizim ichida; sozlansa e-pochtaga ham; takroriy eslatmalar yuborilmaydi |
| 6 Xavfsizlik | autentifikatsiya, parol siyosati, kirish urinishlarini cheklash, rollar, harakatlar jurnali (administrator harakatlari alohida belgilanadi), o‘zgarishlar tarixi, HTTPS sozlamalari, zaxira nusxa va tiklash |
| 7 Hisobot va monitoring | hisobot shablonlari kunlik/haftalik/oylik/choraklik/yillik avtomatik shakllantiriladi va arxivda saqlanadi |
| 8 Integratsiya | jadval2.sud.uz; manba, olingan va yangilangan vaqt qayd etiladi; e-pochta; tashkilotlar Excel orqali |
| 9 Texnik bo‘lmagan talablar | o‘zbek (lotin) interfeysi, moslashuvchan dizayn, klassifikatorlar koddan tashqari boshqariladi |

## 6. Boshqaruv buyruqlari

| Buyruq | Vazifasi |
|---|---|
| `migrate` | bazani yaratish/yangilash (klassifikatorlar avtomatik qo‘shiladi) |
| `load_demo [--cases N]` | sinov ma’lumotlari |
| `import_organizations fayl.xlsx` | tashkilotlar ma’lumotnomasini import qilish |
| `run_integration [--all] [--source ID]` | integratsiya manbalarini tekshirish |
| `send_reminders` | majlis/muddat eslatmalari, muddati o‘tganlar, yangilanmagan ishlar |
| `generate_reports [--force]` | davriy hisobotlar |
| `backup [--keep N]` | zaxira nusxa (ma’lumotlar + hujjatlar), eskilari tozalanadi |
| `restore fayl.zip` | zaxira nusxadan tiklash (oldin joriy holatning nusxasi olinadi) |
| `run_scheduler` | yuqoridagi fon vazifalarini jadval asosida bajaruvchi jarayon |

## 7. Loyiha tuzilishi

```
sud_monitoringi/
├── config/          sozlamalar va URL’lar
├── accounts/        foydalanuvchilar, rollar, harakatlar jurnali, zaxira nusxa
├── core/            klassifikatorlar, tashkilotlar, sudlar, nomlarni normallashtirish
├── cases/           sud ishi kartochkasi, bosqichlar, majlislar, muddatlar, hujjatlar, tarix
├── integration/     manbalar, adapterlar, tashkilotlarni moslash, qayta ishlash
├── notifications/   xabarnomalar va eslatmalar
├── reports/         dashboard, hisobotlar, Excel/PDF eksport
├── templates/       HTML shablonlar
└── static/          CSS, JS, Bootstrap, Chart.js, shriftlar (lokal)
```
