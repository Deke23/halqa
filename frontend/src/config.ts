/** The only place the product name is written. */
export const APP_NAME = "Halqa";

export const LANGUAGES = ["en", "ar", "fr"] as const;
export type Language = (typeof LANGUAGES)[number];
export const RTL_LANGUAGES: readonly Language[] = ["ar"];
