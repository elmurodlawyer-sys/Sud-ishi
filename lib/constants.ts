export type Option = { value: string; label: string };

export const STATUSES: Option[] = [
  { value: "yangi", label: "Yangi" },
  { value: "korilmoqda", label: "Ko'rib chiqilmoqda" },
  { value: "toxtatilgan", label: "To'xtatilgan" },
  { value: "hal_qilingan", label: "Hal qilingan" },
  { value: "apellyatsiya", label: "Apellyatsiyada" },
  { value: "kassatsiya", label: "Kassatsiyada" },
  { value: "ijroda", label: "Ijroda" },
  { value: "yopilgan", label: "Yopilgan" },
];

/** Hali yakunlanmagan (faol) holatlar. */
export const ACTIVE_STATUSES = ["yangi", "korilmoqda", "toxtatilgan", "apellyatsiya", "kassatsiya", "ijroda"];

export const CATEGORIES: Option[] = [
  { value: "fuqarolik", label: "Fuqarolik" },
  { value: "iqtisodiy", label: "Iqtisodiy" },
  { value: "mamuriy", label: "Ma'muriy" },
  { value: "jinoyat", label: "Jinoyat" },
];

export const ROLES: Option[] = [
  { value: "davogar", label: "Da'vogar" },
  { value: "javobgar", label: "Javobgar" },
  { value: "uchinchi_shaxs", label: "Uchinchi shaxs" },
  { value: "arizachi", label: "Arizachi" },
];

export const OUTCOMES: Option[] = [
  { value: "", label: "—" },
  { value: "foydaga", label: "Foydaga" },
  { value: "zararga", label: "Zararga" },
  { value: "qisman", label: "Qisman" },
  { value: "kelishuv", label: "Kelishuv bitimi" },
  { value: "korilmasdan", label: "Ko'rilmasdan qoldirilgan" },
];

export const REGIONS: string[] = [
  "Qoraqalpog'iston Respublikasi",
  "Andijon viloyati",
  "Buxoro viloyati",
  "Farg'ona viloyati",
  "Jizzax viloyati",
  "Xorazm viloyati",
  "Namangan viloyati",
  "Navoiy viloyati",
  "Qashqadaryo viloyati",
  "Samarqand viloyati",
  "Sirdaryo viloyati",
  "Surxondaryo viloyati",
  "Toshkent viloyati",
  "Toshkent shahri",
];

export function labelOf(options: Option[], value: string | null | undefined): string {
  return options.find((o) => o.value === value)?.label ?? value ?? "";
}
