import type { Locale } from "@/lib/i18n";

export function formatDate(value: string | null, locale: Locale) {
  if (!value) return "—";
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-IQ" : "en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatDuration(milliseconds: number, locale: Locale) {
  if (milliseconds < 1000) return `${Math.round(milliseconds)} ms`;
  return `${new Intl.NumberFormat(locale).format(milliseconds / 1000)} s`;
}

export function formatNumber(value: number, locale: Locale, digits = 0) {
  return new Intl.NumberFormat(locale === "ar" ? "ar-IQ" : "en-GB", {
    maximumFractionDigits: digits,
  }).format(value);
}
