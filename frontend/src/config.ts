/** The only place the product name is written. */
export const APP_NAME = "Halqa";

export const LANGUAGES = ["en", "ar", "fr"] as const;
export type Language = (typeof LANGUAGES)[number];
export const RTL_LANGUAGES: readonly Language[] = ["ar"];

/** Arabic rendering of the product name, shown on Arabic screens in place of the Latin name. */
export const APP_NAME_AR = "حلقة";
