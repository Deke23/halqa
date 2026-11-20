import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/api/auth";
import {
  Badge,
  Card,
  DueChip,
  EmptyState,
  ErrorState,
  Loading,
  StateBadge,
  Table,
  Tag,
  type Column,
} from "@/components";
import { formatDateTime } from "@/lib/format";
import { pickText } from "@/lib/i18nField";
import { useCaseList, useMyEconsults, useMyUserId } from "../api";
import { CaseRing } from "../CaseRing";
import { useLabels } from "../labels";
import { usePersonText } from "../PersonLabel";
import type { CaseSummary, EConsult } from "../types";

const READY_LABELS = ["consider_closure", "clinician_closure_decision"];

export default function StaffWorklist() {
  const { t, i18n } = useTranslation("staff");
  const { t: tc } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();
  const labels = useLabels();
  const person = usePersonText();
  const list = useCaseList(user?.region ?? "");
  const econsults = useMyEconsults(!!user);

  const cases = list.data?.cases ?? [];
  const open = cases.filter((c) => c.state !== "CLOSED");
  const me = useMyUserId();

  const urgent = open.filter((c) => c.flags.urgent_review_pending);
  const confirmations = open.filter(
    (c) => c.state === "ACKNOWLEDGED" && c.next_step_label_key === "clinician_review_confirmation" && c.owner_user_id === me,
  );
  const referrals = open.filter((c) => c.state === "REFERRED" && c.next_step_label_key === "accept_referral" && c.owner_user_id === me);
  const ready = open.filter(
    (c) => c.flags.closure_ready || c.flags.needs_clinician_decision || READY_LABELS.includes(c.next_step_label_key ?? ""),
  );
  const consentDecisions = open.filter((c) => c.flags.care_coordination_withdrawn);
  const openEconsults = (econsults.data ?? []).filter((e) => e.status === "OPEN");

  const caseColumns: Column<CaseSummary>[] = [
    {
      key: "patient",
      header: t("queue.cols.patient"),
      cell: (c) => (
        <div className="flex items-center gap-2.5">
          <CaseRing state={c.state} urgent={c.urgent} size={30} />
          <div>
            <Link
              to={`/staff/cases/${c.id}`}
              onClick={(e) => e.stopPropagation()}
              className="font-semibold text-accent-ink underline-offset-2 hover:underline"
              aria-label={t("queue.openCase", { initials: pickText(c.patient_initials_i18n, c.patient_initials), id: c.id })}
            >
              <bdi>{pickText(c.patient_initials_i18n, c.patient_initials)}</bdi>
            </Link>
            <p className="readout whitespace-nowrap text-xs text-muted">
              {c.age_band} · {c.index_systolic}/{c.index_diastolic}
            </p>
          </div>
        </div>
      ),
    },
    {
      key: "state",
      header: t("queue.cols.state"),
      cell: (c) => (
        <div className="flex flex-col items-start gap-1">
          <StateBadge state={c.state} />
          {c.urgent && <Badge tone="urgent">{tc("urgent")}</Badge>}
        </div>
      ),
    },
    {
      key: "next",
      header: t("queue.cols.nextWhy"),
      cell: (c) => (
        <div>
          <p className="font-medium">{labels.nextStep(c.next_step_label_key)}</p>
          <p className="max-w-[14rem] truncate text-xs text-muted" title={labels.reason(c.reason_code)}>
            {labels.reason(c.reason_code)}
          </p>
        </div>
      ),
    },
    {
      key: "due",
      header: t("queue.cols.due"),
      cell: (c) => (
        <div className="flex flex-col items-start gap-1">
          <DueChip dueAt={c.due_at} overdue={c.overdue} className="whitespace-nowrap" />
          {c.due_at && <span className="text-xs text-muted">{formatDateTime(c.due_at, i18n.language)}</span>}
        </div>
      ),
    },
  ];

  const econsultColumns: Column<EConsult>[] = [
    {
      key: "case",
      header: t("worklist.cols.case"),
      cell: (e) => (
        <Link
          to={`/staff/cases/${e.case_id}`}
          onClick={(x) => x.stopPropagation()}
          className="font-semibold text-accent-ink underline-offset-2 hover:underline"
        >
          {t("worklist.caseNumber", { id: e.case_id })}
        </Link>
      ),
    },
    { key: "question", header: t("econsult.questionLabel"), cell: (e) => <span className="line-clamp-2 max-w-md">{e.question}</span> },
    { key: "route", header: t("worklist.cols.route"), cell: (e) => t("econsult.route", { from: person(e.from_person), to: person(e.to_person) }) },
    {
      key: "dir",
      header: t("worklist.cols.direction"),
      cell: (e) => (e.to_user_id === me ? <Badge tone="due">{t("worklist.askedOfMe")}</Badge> : <Badge>{t("worklist.waitingOn")}</Badge>),
    },
    { key: "when", header: t("worklist.cols.asked"), cell: (e) => formatDateTime(e.created_at, i18n.language) },
  ];

  const sections: Array<{ id: string; title: string; hint: string; rows: CaseSummary[] }> = [
    { id: "urgent", title: t("worklist.urgent"), hint: t("worklist.urgentHint"), rows: urgent },
    { id: "confirmations", title: t("worklist.confirmations"), hint: t("worklist.confirmationsHint"), rows: confirmations },
    { id: "referrals", title: t("worklist.referrals"), hint: t("worklist.referralsHint"), rows: referrals },
    { id: "consent", title: t("worklist.consent"), hint: t("worklist.consentHint"), rows: consentDecisions },
  ];

  if (list.isLoading) return <Loading />;
  if (list.error) return <ErrorState error={list.error} onRetry={() => void list.refetch()} />;

  const section = (id: string, title: string, hint: string, count: number, body: React.ReactNode) => (
    <section key={id} aria-labelledby={`wl-${id}`}>
      <Card
        title={<span id={`wl-${id}`}>{title}</span>}
        action={<Badge tone={count > 0 ? "accent" : "neutral"}>{count}</Badge>}
        padded
      >
        <p className="mb-3 text-sm text-muted">{hint}</p>
        {body}
      </Card>
    </section>
  );

  return (
    <div className="flex flex-col gap-5">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{t("worklist.title")}</h1>
        {user && <Tag>{tc(user.region === "YDE" ? "regions.yaounde" : "regions.abu_dhabi")}</Tag>}
      </header>
      <p className="max-w-prose text-sm text-muted">{t("worklist.intro")}</p>

      {sections.map((s) =>
        section(
          s.id,
          s.title,
          s.hint,
          s.rows.length,
          s.rows.length === 0 ? (
            <EmptyState description={t("worklist.emptySection")} />
          ) : (
            <Table
              caption={s.title}
              columns={caseColumns}
              rows={s.rows}
              rowKey={(c) => c.id}
              onRowClick={(c) => navigate(`/staff/cases/${c.id}`)}
            />
          ),
        ),
      )}

      {section(
        "econsults",
        t("worklist.econsults"),
        t("worklist.econsultsHint"),
        openEconsults.length,
        econsults.isLoading ? (
          <Loading />
        ) : econsults.error ? (
          <ErrorState error={econsults.error} onRetry={() => void econsults.refetch()} />
        ) : openEconsults.length === 0 ? (
          <EmptyState description={t("worklist.emptySection")} />
        ) : (
          <Table
            caption={t("worklist.econsults")}
            columns={econsultColumns}
            rows={openEconsults}
            rowKey={(e) => e.id}
            onRowClick={(e) => navigate(`/staff/cases/${e.case_id}`)}
          />
        ),
      )}

      {section(
        "ready",
        t("worklist.ready"),
        t("worklist.readyHint"),
        ready.length,
        ready.length === 0 ? (
          <EmptyState description={t("worklist.emptySection")} />
        ) : (
          <Table
            caption={t("worklist.ready")}
            columns={caseColumns}
            rows={ready}
            rowKey={(c) => c.id}
            onRowClick={(c) => navigate(`/staff/cases/${c.id}`)}
          />
        ),
      )}
    </div>
  );
}
