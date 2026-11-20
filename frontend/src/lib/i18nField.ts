import i18next from "i18next";

/**
 * Server-supplied display text arrives as a plain string plus a map per language
 * (`names`, `label_i18n`, `basis_i18n`, and so on). These helpers pick the right one
 * for the current interface language and fall back to the plain string.
 */
export type I18nText = Partial<Record<"en" | "ar" | "fr", string | null>> | null | undefined;

function base(lang: string | undefined): "en" | "ar" | "fr" {
  const l = (lang ?? i18next.language ?? "en").slice(0, 2);
  return l === "ar" || l === "fr" ? l : "en";
}

/** Text for the current language, or the fallback when the map has no entry. */
export function pickText(map: I18nText, fallback?: string | null, lang?: string): string {
  const l = base(lang);
  return map?.[l] || fallback || map?.en || "";
}

type PersonLike = { name?: string | null; names?: I18nText; display_name?: string | null } | null | undefined;

/** A person's name in the script of the current language. */
export function personName(person: PersonLike, lang?: string): string {
  if (!person) return "";
  return pickText(person.names, person.display_name ?? person.name ?? "", lang);
}
