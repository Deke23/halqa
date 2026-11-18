import { useTranslation } from "react-i18next";
import { EmptyState, ErrorState, Loading, SimulatedTag, Tag } from "@/components";
import { formatDateTime } from "@/lib/format";
import { useThread } from "./api";
import { PageTitle, plainName } from "./ui";

export default function Messages() {
  const { t, i18n } = useTranslation("patient");
  const q = useThread(i18n.language);
  const items = [...(q.data ?? [])].reverse();

  return (
    <div className="flex flex-col gap-4">
      <PageTitle>{t("messages.heading")}</PageTitle>
      <p className="text-muted">{t("messages.intro")}</p>
      {q.isLoading ? (
        <Loading />
      ) : q.error ? (
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState description={t("messages.empty")} />
      ) : (
        <ul className="m-0 flex list-none flex-col gap-3 p-0">
          {items.map((m) => (
            <li key={m.id} className="rounded-card border border-line bg-surface p-4 shadow-card">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-sm text-muted">
                <span className="font-medium text-ink">
                  <bdi>
                    {m.direction === "IN"
                      ? t("messages.you")
                      : m.sender_name
                        ? t("messages.from", { name: plainName(m.sender_name) })
                        : t("messages.fromTeam")}
                  </bdi>
                </span>
                <span>
                  <bdi>{formatDateTime(m.created_at, i18n.language)}</bdi>
                </span>
                {m.channel !== "APP" && <SimulatedTag label={m.channel === "SMS" ? "SMS" : "WhatsApp"} />}
              </div>
              <p className="m-0 whitespace-pre-line leading-relaxed">{m.text}</p>
              <div className="mt-2">
                <Tag>
                  {m.source === "AI_REWORDED"
                    ? t("messages.aiReworded", { name: m.approved_by_name ?? "" })
                    : t("messages.standard")}
                </Tag>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
