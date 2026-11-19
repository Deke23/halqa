import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import {
  Badge,
  BPReading,
  DueChip,
  EmptyState,
  ErrorState,
  Loading,
  StateBadge,
  Table,
  Tabs,
  Tag,
  type Column,
} from "@/components";
import { formatDateTime } from "@/lib/format";
import { useCaseList } from "../api";
import { OwnerCell } from "../PersonLabel";
import { useLabels } from "../labels";
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
  const setTab = setChosen;
  const rows = byTab[tab];

  const columns: Column<CaseSummary>[] = [
    {
      key: "patient",
      header: t("queue.cols.patient"),
      cell: (c) => (
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Link
              to={`/staff/cases/${c.id}`}
              onClick={(e) => e.stopPropagation()}
              className="font-semibold text-accent-ink underline-offset-2 hover:underline"
              aria-label={t("queue.openCase", { initials: c.patient_initials, id: c.id })}
            >
              {c.patient_initials}
            </Link>
            <span className="text-xs text-muted">{t("queue.ageBand", { band: `⁦${c.age_band}⁩` })}</span>
            {c.id === newId && <Badge tone="accent">{t("queue.new")}</Badge>}
          </div>
          <p className="text-xs text-muted">
            <bdi dir="ltr" className="clinical">
              {c.patient_ref}
            </bdi>{" "}
            {c.language.toUpperCase()}
          </p>
        </div>
      ),
    },
    {
      key: "reading",
      header: t("queue.cols.reading"),
      cell: (c) => <BPReading systolic={c.index_systolic} diastolic={c.index_diastolic} size="sm" />,
    },
    {
      key: "state",
      header: t("queue.cols.state"),
      cell: (c) => (
        <div className="flex flex-col items-start gap-1">
          <StateBadge state={c.state} />
          {c.urgent && c.state !== "CLOSED" && <Badge tone="urgent">{tc("urgent")}</Badge>}
        </div>
      ),
    },
    { key: "next", header: t("queue.cols.next"), cell: (c) => labels.nextStep(c.next_step_label_key) },
    { key: "owner", header: t("queue.cols.owner"), cell: (c) => <OwnerCell person={c.owner_person} role={c.owner_role} /> },
    {
      key: "due",
      header: t("queue.cols.due"),
      cell: (c) =>
        c.state === "CLOSED" ? (
          <span className="text-muted">{t("queue.closed")}</span>
        ) : (
          <div className="flex flex-col items-start gap-1">
            <DueChip dueAt={c.due_at} overdue={c.overdue} className="whitespace-nowrap" />
            {c.due_at && <span className="text-xs text-muted">{formatDateTime(c.due_at, i18n.language)}</span>}
            {c.escalation_level > 0 && <Badge tone="urgent">{t("queue.escalationLevel", { level: c.escalation_level })}</Badge>}
          </div>
        ),
    },
    {
      key: "why",
      header: t("queue.cols.why"),
      cell: (c) => {
        const extra: string[] = [];
        if (c.rejection_reason) extra.push(t("queue.rejectionReason", { reason: c.rejection_reason }));
        if (c.escalation_reason && c.flags.escalated) extra.push(t("queue.escalationReason", { reason: c.escalation_reason }));
        if (c.last_contact_attempt && c.last_contact_attempt_at && c.state !== "CLOSED")
          extra.push(t("queue.lastContact", { what: labels.contact(c.last_contact_attempt), when: formatDateTime(c.last_contact_attempt_at, i18n.language) }));
        return (
          <div className="max-w-64">
            <p>{labels.reason(c.reason_code)}</p>
            {extra.map((x) => (
              <p key={x} className="mt-0.5 text-xs text-muted">
                {x}
              </p>
            ))}
          </div>
        );
      },
    },
  ];

  const tabItems = TABS.map((id) => ({ id, label: tc(`queues.${id}`), count: byTab[id].length }));

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{t("queue.title")}</h1>
        {user && <Tag>{tc(user.region === "YDE" ? "regions.yaounde" : "regions.abu_dhabi")}</Tag>}
      </header>
      <p className="max-w-prose text-sm text-muted">{t("queue.intro")}</p>

      {user && (user.region === "AUH" || user.region === "YDE") && (
        <SimulatePanel
          region={user.region}
          onLanded={(id, severe) => {
            setNewId(id);
            setTab(severe ? "urgent" : "all");
          }}
        />
      )}

      <section aria-labelledby="queue-list">
        <h2 id="queue-list" className="sr-only">
          {t("queue.listHeading")}
        </h2>
        <Tabs label={t("queue.tabsLabel")} tabs={tabItems} value={tab} onChange={(id) => setTab(id as Tab)} panelId="queue-panel" />
        <div id="queue-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="mt-4">
          {list.isLoading && <Loading />}
          {list.error && <ErrorState error={list.error} onRetry={() => void list.refetch()} />}
          {list.data && rows.length === 0 && <EmptyState description={t(`queue.empty.${tab}`)} />}
          {list.data && rows.length > 0 && (
            <Table
              caption={t("queue.tableCaption", { queue: tc(`queues.${tab}`) })}
              columns={columns}
              rows={rows}
              rowKey={(c) => c.id}
              onRowClick={(c) => navigate(`/staff/cases/${c.id}`)}
            />
          )}
        </div>
      </section>
    </div>
  );
}
