import { useTranslation } from "react-i18next";
import { Card } from "./Card";

export interface PlaceholderProps {
  title: string;
  /** Which workstream builds this screen. */
  owner: string;
  route: string;
}

/** Temporary page body. The owning workstream replaces it. */
export function Placeholder({ title, owner, route }: PlaceholderProps) {
  const { t } = useTranslation();
  return (
    <Card title={title}>
      <p>{t("placeholder.ownedBy", { owner })}</p>
      <p className="mt-1 text-sm text-muted">
        <span className="clinical">{t("placeholder.route", { route })}</span>
      </p>
    </Card>
  );
}
