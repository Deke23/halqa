import { useTranslation } from "react-i18next";
import { usePersonas } from "@/api/hooks";

function cap(s: string, lng: string): string {
  return lng.startsWith("ar") || !s ? s : s.charAt(0).toUpperCase() + s.slice(1);
}

/**
 * Persona name, role and description for display. Prefers the server's display_names and
 * role_titles (GET /api/personas) and falls back to the locale text when the request fails.
 */
export function usePersonaText() {
  const { t, i18n } = useTranslation();
  const q = usePersonas();
  const lng = i18n.language.slice(0, 2);
  return (key: string) => {
    const s = q.data?.find((p) => p.persona === key);
    return {
      name: s?.display_names?.[lng] || s?.display_name || t(`personas.${key}.name`),
      role: s?.role_titles?.[lng] ? cap(s.role_titles[lng]!, lng) : t(`personas.${key}.role`),
      description: t(`personas.${key}.description`),
    };
  };
}
