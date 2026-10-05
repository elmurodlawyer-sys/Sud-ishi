/**
 * Sud qarorlari monitoringi: public.sud.uz ochiq API'sidan Ijtimoiy himoya tizimi
 * tashkilotlari ishtirok etgan qarorlarni topib, joriy Google Sheet'ga yozadi.
 *
 * Ishga tushirish (trigger yo'q, faqat siz xohlagan paytda):
 *  - Sheet'da "Sud qarorlari" menyusi orqali; yoki
 *  - veb-ilova orqali (Развернуть -> Новое развертывание -> Веб-приложение).
 * Kerakli xizmat: chap paneldagi "Сервисы" -> Drive API (v3, identifikator "Drive").
 */

const API = 'https://adolatapi1.sud.uz';
const TIME_BUDGET_MS = 4.5 * 60 * 1000; // Apps Script chegarasi 6 daqiqa; zaxira bilan to'xtaymiz.
const SHEET = 'Qarorlar';
const CHECKED = '_tekshirilgan';

// Fuqarolik ishlarida tizim tashkilotlari ko'p uchraydigan toifalar; ma'muriy ishlarda barcha toifalar.
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
const TYPE_LABEL = {ADMINISTRATIVE: "Ma'muriy", CIVIL: 'Fuqarolik'};
const RESULT_LABEL = {FULFILLED: 'Qanoatlantirilgan', PARTIALLY_FULFILLED: 'Qisman', REFUSED: 'Rad etilgan',
  CASE_ENDED: 'Tugatilgan', LEFT_WITHOUT_CONSIDERATION: "Ko'rmasdan qoldirilgan"};

// ---------- Sheet menyusi ----------

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Sud qarorlari')
    .addItem('Oxirgi 7 kunni qidirish', 'qidirish7')
    .addItem('Oxirgi 30 kunni qidirish', 'qidirish30')
    .addItem('Sanalarni kiritib qidirish…', 'qidirishSana')
    .addToUi();
}

function qidirish7() { menuRun_(daysAgo_(7), ymd_(new Date())); }
function qidirish30() { menuRun_(daysAgo_(30), ymd_(new Date())); }

function qidirishSana() {
  const ui = SpreadsheetApp.getUi();
  const a = ui.prompt('Boshlanish sanasi', 'YYYY-MM-DD, masalan 2026-09-01', ui.ButtonSet.OK_CANCEL);
  if (a.getSelectedButton() !== ui.Button.OK) return;
  const b = ui.prompt('Tugash sanasi', 'YYYY-MM-DD, masalan 2026-09-30', ui.ButtonSet.OK_CANCEL);
  if (b.getSelectedButton() !== ui.Button.OK) return;
  menuRun_(a.getResponseText().trim(), b.getResponseText().trim());
}

function menuRun_(from, to) {
  const r = searchChunk(from, to, ['ADMINISTRATIVE', 'CIVIL']);
  SpreadsheetApp.getUi().alert(
    'Tekshirildi: ' + r.checked + ' ta qaror, topildi: ' + r.found + ' ta.' +
    (r.remaining ? '\nYana ' + r.remaining + ' ta qaror qoldi: menyu bandini qayta bosing.' : '\nDavr to\'liq tekshirildi.'));
}

// ---------- Veb-ilova ----------

function doGet() {
  return HtmlService.createTemplateFromFile('Index').evaluate()
    .setTitle('Sud qarorlari monitoringi')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/** Veb-ilova uchun: barcha topilgan qatorlar. */
function getRows() {
  const sh = sheet_();
  if (sh.getLastRow() < 2) return [];
  return sh.getRange(2, 1, sh.getLastRow() - 1, HEADER.length).getDisplayValues()
    .map(r => ({type: r[0], number: r[1], court: r[2], instance: r[3], date: r[4], category: r[5],
      result: r[6], role: r[7], snippet: r[8], pdf: r[9]}));
}

/**
 * Bir bo'lak qidiruv: vaqt chegarasigacha qarorlarni o'qiydi va qolganlar sonini qaytaradi.
 * Veb-ilova uni remaining = 0 bo'lguncha qayta chaqiradi.
 */
function searchChunk(from, to, types) {
  const startedAt = Date.now();
  const sh = sheet_();
  const checkedSh = checkedSheet_();
  const checked = new Set(checkedSh.getLastRow() ? checkedSh.getRange(1, 1, checkedSh.getLastRow(), 1).getValues().flat() : []);
  const todo = [];
  for (const t of types) {
    for (const cat of CATEGORIES[t]) {
      for (const item of list_(t, cat, from, to)) {
        if (item.pdf && !checked.has(item.id)) todo.push([t, item]);
      }
    }
  }
  let done = 0, found = 0;
  const newChecked = [];
  for (const [t, item] of todo) {
    if (Date.now() - startedAt > TIME_BUDGET_MS) break;
    try {
      const flat = pdfText_(item.pdf.id).replace(/\s+/g, ' ');
      const m = flat.match(ORG);
      if (m) {
        const i = flat.indexOf(m[0]);
        sh.appendRow([
          TYPE_LABEL[t] || t, item.case_number, (item.court_names || {}).uz_cyr || '', item.instance,
          item.hearing_date || '', (item.categories || []).map(c => c.uz_cyr).join('; '),
          RESULT_LABEL[item.result] || item.result, role_(flat),
          flat.substring(Math.max(0, i - 200), i + 300), API + '/public/onStream/' + item.pdf.id, item.id,
        ]);
        found++;
      }
      newChecked.push([item.id]);
      done++;
    } catch (e) {
      console.warn(item.case_number + ': ' + e);
    }
  }
  if (newChecked.length) checkedSh.getRange(checkedSh.getLastRow() + 1, 1, newChecked.length, 1).setValues(newChecked);
  return {checked: done, found: found, remaining: todo.length - done};
}

// ---------- Sinov funksiyalari ----------

function testApi() {
  const d = JSON.parse(UrlFetchApp.fetch(API + '/publications/list?court_type=ADMINISTRATIVE&page=0&size=1').getContentText());
  Logger.log('API ishlayapti. Ma\'muriy qarorlar soni: ' + d.totalElements + ', birinchisi: ' + d.content[0].case_number);
}

function testPdf() {
  const d = JSON.parse(UrlFetchApp.fetch(API + '/publications/list?court_type=ADMINISTRATIVE&page=0&size=1').getContentText());
  const text = pdfText_(d.content[0].pdf.id);
  Logger.log('PDF matni o\'qildi, ' + text.length + ' belgi. Boshi: ' + text.substring(0, 300));
}

// ---------- Yordamchi funksiyalar ----------

function list_(courtType, cat, from, to) {
  const out = [];
  for (let page = 0; page < 50; page++) {
    let url = API + '/publications/list?court_type=' + courtType + '&size=100&page=' + page +
      '&startDate=' + from + '&endDate=' + to;
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
  if (last[0] === 'davogar' && /манфаат/i.test(after)) return 'vakil';
  return last[0];
}

function sheet_() {
  const ss = SpreadsheetApp.getActive() || SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty('SHEET_ID'));
  const sh = ss.getSheetByName(SHEET) || ss.insertSheet(SHEET);
  if (sh.getLastRow() === 0) sh.appendRow(HEADER).setFrozenRows(1);
  return sh;
}

function checkedSheet_() {
  const ss = sheet_().getParent();
  let sh = ss.getSheetByName(CHECKED);
  if (!sh) { sh = ss.insertSheet(CHECKED); sh.hideSheet(); }
  return sh;
}

function daysAgo_(n) {
  return ymd_(new Date(Date.now() - n * 86400000));
}

function ymd_(d) {
  return Utilities.formatDate(d, 'Asia/Tashkent', 'yyyy-MM-dd');
}
// KOD OXIRI (v3)
