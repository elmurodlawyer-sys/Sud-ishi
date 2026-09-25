# Sud-ishi

Sud ishi monitoring tizimi — boshqarma ishtirok etayotgan sud ishlarini ro'yxatga olish, sud majlislari va muddatlarni kuzatish uchun veb-ilova.

## Imkoniyatlar

- **Boshqaruv paneli** — jami/faol ishlar, faol da'volar summasi, 7 kunlik majlislar, natijasi kiritilmagan majlislar, yaqinlashayotgan shikoyat muddatlari; holat, ish turi, natija va hududlar kesimidagi statistika.
- **Ishlar** — qidiruv (raqam, taraflar, sud, predmet, mas'ul) hamda holat / tur / rol / hudud bo'yicha filtr va saralash.
- **Ish kartochkasi** — to'liq ma'lumot, sud majlislarini qo'shish va natijasini kiritish, o'zgarishlar tarixi (holat, natija, muddat o'zgarishlari avtomatik yoziladi).
- **Sud majlislari** — kelgusi, natijasi kiritilmagan va o'tgan majlislar ro'yxati.

## Texnologiyalar

Next.js 16 (App Router, Server Actions), React 19, TypeScript, SQLite (`better-sqlite3`).

## Ishga tushirish

```bash
npm install
npm run seed      # ixtiyoriy: namuna ma'lumotlar (qayta to'ldirish: npm run seed -- --force)
npm run dev       # http://localhost:3000
```

Production: `npm run build && npm start`.

Ma'lumotlar bazasi `data/sud.db` faylida saqlanadi (`DATABASE_PATH` muhit o'zgaruvchisi bilan o'zgartirish mumkin). Jadval tuzilmasi — `lib/schema.sql`.

## Tuzilma

```
app/              sahifalar va server actions (app/actions.ts)
components/       umumiy UI komponentlar
lib/              DB ulanishi, so'rovlar (cases.ts), ma'lumotnomalar (constants.ts)
scripts/seed.mjs  namuna ma'lumotlar
```
