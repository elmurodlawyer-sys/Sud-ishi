// Namuna ma'lumotlar bilan bazani to'ldirish: npm run seed
import Database from "better-sqlite3";
import fs from "node:fs";
import path from "node:path";

const dbPath = process.env.DATABASE_PATH ?? path.join(process.cwd(), "data", "sud.db");
fs.mkdirSync(path.dirname(dbPath), { recursive: true });
const db = new Database(dbPath);
db.pragma("foreign_keys = ON");
db.exec(fs.readFileSync(path.join(process.cwd(), "lib", "schema.sql"), "utf8"));

if (db.prepare("SELECT COUNT(*) AS n FROM cases").get().n > 0 && !process.argv.includes("--force")) {
  console.log("Bazada allaqachon ma'lumot bor. Qayta to'ldirish uchun: npm run seed -- --force");
  process.exit(0);
}
db.exec("DELETE FROM case_events; DELETE FROM hearings; DELETE FROM cases;");

const pad = (n) => String(n).padStart(2, "0");
const day = (offset, time) => {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  const s = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  return time ? `${s}T${time}` : s;
};

const cases = [
  { case_number: "4-1001-2601/1245", court: "Toshkent shahar iqtisodiy sudi", category: "iqtisodiy", role: "davogar",
    region: "Toshkent shahri", plaintiff: "Boshqarma", defendant: "\"Qurilish Invest\" MChJ",
    subject: "Shartnoma bo'yicha qarzdorlik va penyani undirish", claim_amount: 184500000, judge: "A. Karimov",
    responsible: "D. Rahimova", status: "korilmoqda", filed_at: day(-40),
    hearings: [[-12, "10:00", "3-zal", "Ish keyinga qoldirildi, javobgardan hujjatlar so'raldi"], [3, "11:30", "3-zal", null]] },
  { case_number: "2-1502-2601/318", court: "Samarqand tumanlararo fuqarolik sudi", category: "fuqarolik", role: "javobgar",
    region: "Samarqand viloyati", plaintiff: "S. Norqulov", defendant: "Boshqarma",
    subject: "Ishga tiklash va majburiy progul haqini undirish", claim_amount: 24000000, judge: "M. Xolmatova",
    responsible: "B. Ergashev", status: "korilmoqda", filed_at: day(-25),
    hearings: [[-2, "14:00", "5-zal", null], [9, "09:30", "5-zal", null]] },
  { case_number: "3-1203-2601/77", court: "Farg'ona viloyati ma'muriy sudi", category: "mamuriy", role: "javobgar",
    region: "Farg'ona viloyati", plaintiff: "\"Agro Farg'ona\" MChJ", defendant: "Boshqarma",
    subject: "Ma'muriy hujjatni haqiqiy emas deb topish", claim_amount: null, judge: "R. Umarov",
    responsible: "D. Rahimova", status: "hal_qilingan", outcome: "foydaga", filed_at: day(-70),
    decision_date: day(-15), appeal_deadline: day(5),
    hearings: [[-30, "10:00", "", "Taraflar tushuntirishlari tinglandi"], [-15, "15:00", "", "Da'vo rad etildi"]] },
  { case_number: "4-1101-2601/902", court: "Andijon viloyati iqtisodiy sudi", category: "iqtisodiy", role: "davogar",
    region: "Andijon viloyati", plaintiff: "Boshqarma", defendant: "\"Andijon Textile\" AJ",
    subject: "Ijara to'lovlari bo'yicha qarzni undirish", claim_amount: 67300000, judge: "",
    responsible: "B. Ergashev", status: "yangi", filed_at: day(-3), hearings: [] },
  { case_number: "4-1401-2501/4410", court: "Buxoro viloyati iqtisodiy sudi", category: "iqtisodiy", role: "davogar",
    region: "Buxoro viloyati", plaintiff: "Boshqarma", defendant: "\"Buxoro Savdo\" MChJ",
    subject: "Yetkazib berilmagan mahsulot uchun avansni qaytarish", claim_amount: 312000000, judge: "Sh. Qodirov",
    responsible: "N. Tursunov", status: "ijroda", outcome: "qisman", filed_at: day(-160),
    decision_date: day(-90), hearings: [[-100, "11:00", "2-zal", "Ekspertiza tayinlandi"], [-90, "11:00", "2-zal", "Da'vo qisman qanoatlantirildi"]] },
  { case_number: "2-1601-2601/55", court: "Toshkent viloyati sudi", category: "fuqarolik", role: "uchinchi_shaxs",
    region: "Toshkent viloyati", plaintiff: "O. Yusupova", defendant: "\"Yangi Uy\" MChJ",
    subject: "Ko'chmas mulkka bo'lgan huquqni tan olish", claim_amount: null, judge: "F. Aliyev",
    responsible: "N. Tursunov", status: "apellyatsiya", outcome: "zararga", filed_at: day(-120),
    decision_date: day(-35), hearings: [[6, "10:00", "Apellyatsiya instansiyasi", null]] },
  { case_number: "4-0901-2501/2033", court: "Navoiy viloyati iqtisodiy sudi", category: "iqtisodiy", role: "javobgar",
    region: "Navoiy viloyati", plaintiff: "\"Navoiy Energo\" AJ", defendant: "Boshqarma",
    subject: "Kommunal xizmatlar uchun qarz", claim_amount: 9800000, judge: "Z. Sobirov",
    responsible: "D. Rahimova", status: "yopilgan", outcome: "kelishuv", filed_at: day(-210),
    decision_date: day(-180), hearings: [[-180, "09:00", "", "Kelishuv bitimi tasdiqlandi"]] },
  { case_number: "3-1701-2601/140", court: "Qashqadaryo viloyati ma'muriy sudi", category: "mamuriy", role: "arizachi",
    region: "Qashqadaryo viloyati", plaintiff: "Boshqarma", defendant: "Qarshi shahar hokimligi",
    subject: "Qarorni bekor qilish to'g'risida ariza", claim_amount: null, judge: "",
    responsible: "B. Ergashev", status: "toxtatilgan", filed_at: day(-50), notes: "Ekspertiza xulosasi kutilmoqda",
    hearings: [[-20, "10:30", "", "Ish yuritish to'xtatildi"]] },
];

const insertCase = db.prepare(`INSERT INTO cases (case_number, court, category, role, region, plaintiff, defendant,
  subject, claim_amount, judge, responsible, status, outcome, filed_at, decision_date, appeal_deadline, notes)
  VALUES (@case_number, @court, @category, @role, @region, @plaintiff, @defendant, @subject, @claim_amount, @judge,
  @responsible, @status, @outcome, @filed_at, @decision_date, @appeal_deadline, @notes)`);
const insertHearing = db.prepare("INSERT INTO hearings (case_id, scheduled_at, location, result) VALUES (?, ?, ?, ?)");
const insertEvent = db.prepare("INSERT INTO case_events (case_id, text) VALUES (?, ?)");

db.transaction(() => {
  for (const { hearings, ...c } of cases) {
    const id = insertCase.run({ outcome: "", decision_date: null, appeal_deadline: null, notes: "", ...c }).lastInsertRowid;
    insertEvent.run(id, "Ish ro'yxatga olindi (namuna ma'lumot)");
    for (const [offset, time, location, result] of hearings) insertHearing.run(id, day(offset, time), location, result);
  }
})();

console.log(`${cases.length} ta namuna ish qo'shildi: ${dbPath}`);
