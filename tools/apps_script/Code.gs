/**
 * Sud qarorlari monitoringi: public.sud.uz ochiq API'sidan Ijtimoiy himoya tizimi
 * tashkilotlari ishtirok etgan qarorlarni topib, joriy Google Sheet'ga yozadi.
 *
 * O'rnatish:
 *  1. Google Sheet oching -> Kengaytmalar -> Apps Script, shu faylni joylang.
 *  2. Chap paneldagi "Xizmatlar" (Services) -> "Drive API" ni qo'shing (PDF matnini olish uchun).
 *  3. setup() ni bir marta ishga tushiring: ruxsat beriladi va har kuni 07:00 da ishlaydigan trigger qo'yiladi.
 *
 * Har ishga tushganda oxirgi DAYS_BACK kundagi qarorlar o'qiladi; avval yozilganlari qayta o'qilmaydi.
 * Apps Script bitta ishga tushishda 6 daqiqa ishlaydi, shuning uchun MAX_PER_RUN chegarasi bor.
 */

const API = 'https://adolatapi1.sud.uz';
const DAYS_BACK = 7;
const MAX_PER_RUN = 60;
const SHEET = 'Qarorlar';

// Fuqarolik ishlarida tizim tashkilotlari ko'p uchraydigan toifalar (bo'sh ro'yxat = barcha toifalar).
const CATEGORIES = {
  ADMINISTRATIVE: [null],
  CIVIL: [
    'f6de1988-ecaf-47d2-8c85-633da71b5752', // Ishga tiklash
    '1d6f38e4-7369-4f36-ad9a-693a9486dbb1', // Ish haqini undirish
    'a176b472-4a66-4ec0-a080-e0551dc1afa0', // Pensiya va ijtimoiy to'lovlar
    'fbfda98e-ea00-4e34-bd9c-30a0a6824eff', // Ortiqcha to'langan pensiya
    '9a6fd5ba-e5d0-452d-a4bb-c438cd2bdb5f', // Davlatga yetkazilgan zarar
    '9f62e15b-a803-42c8-9c05-84b2def3d0dc', // Muomalaga layoqatsiz deb topish
    'c8d70922-f866-42ce-8e39-31691d869b27', // Aliment undirish
  ],
};

// Ba'zi PDF'larda shrift xatosi sababli "и" harfi matndan tushib qoladi ("вилоят" -> "влоят").
// Shuning uchun barcha shablonlarda "и" ixtiyoriy qilinadi.
function rx_(src, flags) {
  return new RegExp(src.replace(/[иИ]/g, '[иИ]?'), flags);
}

const ORG = rx_(
  '(Инсон|Inson)\\s*[»"”\']?\\s*(ижтимоий|ijtimoiy)\\s+(хизмат|xizmat|марказ|markaz)' +
  '|(ижтимоий|ijtimoiy)\\s+(ҳимоя|химоя|himoya)\\s+(миллий\\s+|milliy\\s+)?(агентлиг|agentlig)' +
  '|тиббий-ижтимоий\\s+эксперт\\s+комисси' +
  '|[«"“„]\\s*(Мурувват|Саховат)\\s*[»"”]', 'i');

const HEADER = ['Sud turi', 'Ish raqami', 'Sud', 'Instansiya', 'Sana', 'Toifa', 'Natija',
  'Tashkilot roli', 'Matndan parcha', 'PDF', 'ID'];

/** 1-qadam: sud.uz API'si Google serverlaridan ochilishini tekshiradi. Natija "Bajarish jurnali"da chiqadi. */
function testApi() {
  const d = JSON.parse(UrlFetchApp.fetch(API + '/publications/list?court_type=ADMINISTRATIVE&page=0&size=1').getContentText());
  Logger.log('API ishlayapti. Ma\'muriy qarorlar soni: ' + d.totalElements + ', birinchisi: ' + d.content[0].case_number);
}

/** 2-qadam: bitta PDF matnini o'qishni sinaydi (Drive API xizmati qo'shilgan bo'lishi kerak). */
function testPdf() {
  const d = JSON.parse(UrlFetchApp.fetch(API + '/publications/list?court_type=ADMINISTRATIVE&page=0&size=1').getContentText());
  const text = pdfText_(d.content[0].pdf.id);
  Logger.log('PDF matni o\'qildi, ' + text.length + ' belgi. Boshi: ' + text.substring(0, 300));
}

function setup() {
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('run').timeBased().everyDays(1).atHour(7).create();
  sheet_();
}

function run() {
  const sh = sheet_();
  const seen = new Set(sh.getRange(2, 11, Math.max(sh.getLastRow() - 1, 1), 1).getValues().flat());
  const end = new Date();
  const start = new Date(end.getTime() - DAYS_BACK * 86400000);
  let processed = 0;
  for (const courtType of Object.keys(CATEGORIES)) {
    for (const cat of CATEGORIES[courtType]) {
      for (const item of list_(courtType, cat, start, end)) {
        if (processed >= MAX_PER_RUN) return;
        if (!item.pdf || seen.has(item.id)) continue;
        processed++;
        seen.add(item.id);
        const text = pdfText_(item.pdf.id);
        const flat = text.replace(/\s+/g, ' ');
        const m = flat.match(ORG);
        if (!m) continue;
        const i = flat.indexOf(m[0]);
        sh.appendRow([
          courtType, item.case_number, (item.court_names || {}).uz_cyr || '', item.instance,
          item.hearing_date || '', (item.categories || []).map(c => c.uz_cyr).join('; '), item.result,
          role_(flat), flat.substring(Math.max(0, i - 200), i + 300),
          API + '/public/onStream/' + item.pdf.id, item.id,
        ]);
      }
    }
  }
}

function list_(courtType, cat, start, end) {
  const out = [];
  for (let page = 0; page < 50; page++) {
    let url = API + '/publications/list?court_type=' + courtType + '&size=100&page=' + page +
      '&startDate=' + ymd_(start) + '&endDate=' + ymd_(end);
    if (cat) url += '&category_id=' + cat;
    const d = JSON.parse(UrlFetchApp.fetch(url, {muteHttpExceptions: true}).getContentText());
    const rows = d.content || [];
    out.push(...rows);
    if (!rows.length || (page + 1) * 100 >= (d.totalElements || 0)) break;
    Utilities.sleep(300);
  }
  return out;
}

/** PDF'ni Drive orqali vaqtincha Google Docs'ga aylantirib, matnini oladi. */
function pdfText_(pdfId) {
  // sud.uz PDF'ni "application/octet-stream" turi bilan beradi; Drive uni aylantirishi uchun turni aniq ko'rsatamiz.
  const blob = UrlFetchApp.fetch(API + '/public/onStream/' + pdfId).getBlob()
    .setContentType('application/pdf').setName(pdfId + '.pdf');
  const file = Drive.Files.create({name: pdfId, mimeType: 'application/vnd.google-apps.document'}, blob);
  try {
    return DocumentApp.openById(file.id).getBody().getText().replace(/\u0002/g, 'и');
  } finally {
    Drive.Files.remove(file.id);
  }
}

/** Kirish qismida tashkilot nomidan oldingi so'z bo'yicha rolni aniqlaydi. */
function role_(flat) {
  const cut = flat.search(rx_('А\\s?Н\\s?И?\\s?Қ\\s?Л\\s?А\\s?Д\\s?И|аниқлади'));
  const head = cut > 300 ? flat.substring(0, cut) : flat.substring(0, 4000);
  const m = head.match(ORG);
  if (!m) return 'matnda tilga olingan';
  const i = head.indexOf(m[0]);
  const before = head.substring(Math.max(0, i - 160), i);
  const after = head.substring(i, i + 260);
  const last = [['javobgar', /жавобгар/gi], ['davogar', rx_('даъвогар|аризачи', 'gi')], ['uchinchi shaxs', rx_('учинчи\\s+шахс', 'gi')]]
    .map(([r, rx]) => [r, Math.max(-1, ...[...before.matchAll(rx)].map(x => x.index))])
    .sort((a, b) => b[1] - a[1])[0];
  if (last[1] < 0) return /хулоса/i.test(after) ? 'xulosa beruvchi' : 'boshqa';
  if (last[0] === 'davogar' && /манфаат/i.test(after)) return 'vakil (boshqa shaxs manfaatida)';
  return last[0];
}

function sheet_() {
  const ss = SpreadsheetApp.getActive();
  const sh = ss.getSheetByName(SHEET) || ss.insertSheet(SHEET);
  if (sh.getLastRow() === 0) sh.appendRow(HEADER).setFrozenRows(1);
  return sh;
}

function ymd_(d) {
  return Utilities.formatDate(d, 'Asia/Tashkent', 'yyyy-MM-dd');
}
