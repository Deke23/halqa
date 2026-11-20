import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import { Badge, DueChip, EmptyState, ErrorState, Loading, Tabs, Tag } from "@/components";
import { cx } from "@/lib/cx";
import { pickText } from "@/lib/i18nField";
import { formatDateTime } from "@/lib/format";
import { useCaseList } from "../api";
import { CaseRing } from "../CaseRing";
import { useLabels } from "../labels";
import { OwnerCell } from "../PersonLabel";
import type { CaseSummary } from "../types";
import { SimulatePanel } from "./SimulatePanel";

const TABS = ["urgent", "overdue", "rejected", "unowned", "escalated", "all"] as const;
type Tab = (typeof TABS)[number];

/** The same membership rules the server uses for each queue, applied to the full list so one request gives every count. */
const MEMBER: Record<Tab, (c: CaseSummary) => boolean> = {
  urgent: (c) => c.urgent && c.state !== "CLOSED",
  overdue: (c) => c.flags.overdue && c.state !== "CLOSED",
  rejected: (c) => c.flags.rejected,
  unowned: (c) => c.flags.unowned,
  escalated: (c) => c.escalation_level >= 2 && c.state !== "CLOSED",
  all: () => true,
};

export default function StaffQueue() {
  const { t, i18n } = useTranslation("staff");
  const { t: tc } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const labels = useLabels();
  const region = user?.region ?? "";
  const list = useCaseList(region);
  const [chosen, setChosen] = useState<Tab | null>(null);
  const [newId, setNewId] = useState<number | null>(null);

  const cases = useMemo(() => list.data?.cases ?? [], [list.data]);
  const byTab = useMemo(() => {
    const out = {} as Record<Tab, CaseSummary[]>;
    for (const k of TABS) out[k] = cases.filter(MEMBER[k]);
    return out;
  }, [cases]);
  // Until the user picks a tab, show the first queue that has something in it, urgent first.
  const tab: Tab = chosen ?? TABS.find((k) => byTab[k].length > 0) ?? "all";
  const rows = byTab[tab];

  const tabItems = TABS.map((id) => ({ id, label: tc(`queues.${id}`), count: byTab[id].length }));

  function why(c: CaseSummary): { short: string; full: string } {
    const parts = [labels.reason(c.reason_code)];
    if (c.rejection_reason) parts.push(t("queue.rejectionReason", { reason: c.rejection_reason }));
    if (c.escalation_reason && c.flags.escalated) parts.push(t("queue.escalationReason", { reason: c.escalation_reason }));
    if (c.last_contact_attempt && c.last_contact_attempt_at && c.state !== "CLOSED") {
      parts.push(t("queue.lastContact", { what: labels.contact(c.last_contact_attempt), when: formatDateTime(c.last_contact_attempt_at, i18n.language) }));
    }
    return { short: parts[0]!, full: parts.join(". ") };
  }

  const th = "px-2.5 py-2 text-start text-xs font-semibold text-muted";

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{t("queue.title")}</h1>
        {user && <Tag>{tc(user.region === "YDE" ? "regions.yaounde" : "regions.abu_dhabi")}</Tag>}
        <p className="basis-full text-sm text-muted">{t("queue.intro")}</p>
      </header>

      {user && (user.region === "AUH" || user.region === "YDE") && (
        <SimulatePanel
          region={user.region}
          onLanded={(id, severe) => {
            setNewId(id);
            setChosen(severe ? "urgent" : "all");
          }}
        />
      )}

      <section aria-labelledby="queue-list">
        <h2 id="queue-list" className="sr-only">
          {t("queue.listHeading")}
        </h2>
        <Tabs label={t("queue.tabsLabel")} tabs={tabItems} value={tab} onChange={(id) => setChosen(id as Tab)} panelId="queue-panel" />
        <div id="queue-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="mt-3">
          {list.isLoading && <Loading />}
          {list.error && <ErrorState error={list.error} onRetry={() => void list.refetch()} />}
          {list.data && rows.length === 0 && <EmptyState description={t(`queue.empty.${tab}`)} />}
          {list.data && rows.length > 0 && (
            <div className="overflow-x-auto rounded-card border border-line bg-surface">
              <table className="w-full min-w-[40rem] border-collapse text-sm">
                <caption className="sr-only">{t("queue.tableCaption", { queue: tc(`queues.${tab}`) })}</caption>
                <thead className="border-b border-line bg-surface-2">
                  <tr>
                    <th scope="col" className={cx(th, "w-14")}>
                      <span className="sr-only">{t("queue.cols.progress")}</span>
                    </th>
                    <th scope="col" className={th}>{t("queue.cols.patient")}</th>
                    <th scope="col" className={th}>{t("queue.cols.nextWhy")}</th>
                    <th scope="col" className={th}>{t("queue.cols.owner")}</th>
                    <th scope="col" className={th}>{t("queue.cols.due")}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((c) => {
                    const urgent = c.urgent && c.state !== "CLOSED";
                    const w = why(c);
                    return (
                      <tr
                        key={c.id}
                        className="cursor-pointer border-t border-line hover:bg-accent-soft/40"
                        onClick={() => navigate(`/staff/cases/${c.id}`)}
                      >
                        <td className={cx("py-2 ps-3 pe-1", urgent ? "border-s-4 border-s-urgent" : "border-s-4 border-s-transparent")}>
                          <CaseRing state={c.state} urgent={urgent} size={30} />
                        </td>
                        <td className="px-2.5 py-2">
                          <div className="flex items-center gap-2">
                            <Link
                              to={`/staff/cases/${c.id}`}
                              onClick={(e) => e.stopPropagation()}
                              className="font-semibold text-accent-ink underline-offset-2 hover:underline"
                              aria-label={t("queue.openCase", { initials: pickText(c.patient_initials_i18n, c.patient_initials), id: c.id })}
                            >
                              <bdi>{pickText(c.patient_initials_i18n, c.patient_initials)}</bdi>
                            </Link>
                            <span className="readout whitespace-nowrap text-xs text-muted">{c.age_band}</span>
                            {urgent && <Badge tone="urgent">{tc("urgent")}</Badge>}
                            {c.id === newId && <Badge tone="accent">{t("queue.new")}</Badge>}
                          </div>
                          <p className="readout text-xs text-muted">
                            {c.index_systolic}/{c.index_diastolic}
                          </p>
                        </td>
                        <td className="px-2.5 py-2">
                          <p className="font-medium">{labels.nextStep(c.next_step_label_key)}</p>
                          {c.reason_code !== "ON_TRACK" && (
                            <p className="max-w-[12rem] truncate text-xs text-muted" title={w.full} tabIndex={0}>
                              {w.short}
                            </p>
                          )}
                        </td>
                        <td className="px-2.5 py-2">
                          <OwnerCell person={c.owner_person} role={c.owner_role} />
                        </td>
                        <td className="px-2.5 py-2">
                          {c.state === "CLOSED" ? (
                            <span className="text-muted">{t("queue.closed")}</span>
                          ) : (
                            <div className="flex flex-col items-start gap-0.5">
                              <DueChip dueAt={c.due_at} overdue={c.overdue} className="whitespace-nowrap" />
                              {c.escalation_level > 0 && <span className="text-xs font-medium text-urgent-ink">{t("queue.escalationLevel", { level: c.escalation_level })}</span>}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
