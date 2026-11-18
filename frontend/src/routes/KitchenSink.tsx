import { useMemo, useState } from "react";
import { I18nextProvider, useTranslation } from "react-i18next";
import i18n from "@/i18n";
import { LANGUAGES, type Language } from "@/config";
import type { CaseState, TimelineEvent } from "@/api/types";
import {
  Badge,
  BPReading,
  Button,
  Card,
  ConfirmDialog,
  Drawer,
  DueChip,
  EmptyState,
  ErrorState,
  Field,
  Input,
  JourneySteps,
  JsonViewer,
  LanguageSwitch,
  Loading,
  Modal,
  OwnerChip,
  RadioGroup,
  Select,
  SimulatedTag,
  StatCard,
  StateBadge,
  Table,
  Tabs,
  Tag,
  Textarea,
  Timeline,
  useToast,
  type Column,
} from "@/components";
import { CASE_STATES } from "@/api/types";

const NOW = new Date("2026-03-10T09:00:00Z");
const iso = (hoursFromNow: number) => new Date(NOW.getTime() + hoursFromNow * 3_600_000).toISOString();

const EVENTS: TimelineEvent[] = [
  { id: 1, at: iso(-72), type: "RESULT_ISSUED", actor_role: "system" },
  { id: 2, at: iso(-70), type: "NOTIFIED", actor_name: "Mariam", actor_role: "coordinator" },
  { id: 3, at: iso(-30), type: "ESCALATION_LEVEL_1", actor_role: "system", reason: "Reminder to the owner" },
];

const SAMPLE_JSON = {
  resourceType: "Bundle",
  type: "collection",
  entry: [
    { resource: { resourceType: "Observation", code: { coding: [{ system: "http://loinc.org", code: "85354-9" }] } } },
    { resource: { resourceType: "Task", status: "requested", restriction: { period: { end: "2026-03-11T09:00:00Z" } } } },
  ],
};

interface Row {
  id: number;
  initials: string;
  state: CaseState;
}
const ROWS: Row[] = [
  { id: 1, initials: "KA", state: "NOTIFIED" },
  { id: 2, initials: "JP", state: "CONFIRMED" },
];

function Showcase() {
  const { t } = useTranslation();
  const toast = useToast();
  const [tab, setTab] = useState("urgent");
  const [radio, setRadio] = useState("HBPM");
  const [modal, setModal] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [confirm, setConfirm] = useState(false);

  const cols: Column<Row>[] = [
    { key: "who", header: "ID", cell: (r) => r.initials },
    { key: "state", header: t("states.NOTIFIED"), cell: (r) => <StateBadge state={r.state} /> },
    { key: "due", header: t("due.onTime"), cell: () => <DueChip dueAt={iso(-5)} now={NOW} /> },
  ];

  const h = "mb-2 mt-6 text-sm font-semibold uppercase tracking-wide text-muted";

  return (
    <div className="space-y-2">
      <h3 className={h}>Button</h3>
      <div className="flex flex-wrap gap-2">
        <Button>{t("generic.save")}</Button>
        <Button variant="secondary">{t("generic.cancel")}</Button>
        <Button variant="ghost">{t("generic.back")}</Button>
        <Button variant="danger">{t("actions.escalate")}</Button>
        <Button loading>{t("generic.loading")}</Button>
        <Button disabled>{t("generic.next")}</Button>
      </div>

      <h3 className={h}>Badge, Tag, SimulatedTag, StateBadge</h3>
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{t("queues.all")}</Badge>
        <Badge tone="accent">{t("states.IN_CARE")}</Badge>
        <Badge tone="due">{t("due.dueSoon")}</Badge>
        <Badge tone="urgent">{t("urgent")}</Badge>
        <Badge tone="info">{t("regions.abu_dhabi")}</Badge>
        <Tag>{t("regions.yaounde")}</Tag>
        <SimulatedTag />
      </div>
      <div className="flex flex-wrap gap-2">
        {CASE_STATES.map((s) => (
          <StateBadge key={s} state={s} />
        ))}
      </div>

      <h3 className={h}>DueChip (staff, then patient)</h3>
      <div className="flex flex-wrap gap-2">
        <DueChip dueAt={iso(60)} now={NOW} />
        <DueChip dueAt={iso(10)} now={NOW} />
        <DueChip dueAt={iso(-30)} now={NOW} />
        <DueChip dueAt={iso(-120)} now={NOW} />
        <DueChip dueAt={null} now={NOW} />
        <DueChip dueAt={iso(-30)} now={NOW} audience="patient" />
      </div>

      <h3 className={h}>OwnerChip, BPReading, StatCard</h3>
      <div className="flex flex-wrap items-center gap-4">
        <OwnerChip name={t("personas.coordinator_auh.name")} role="coordinator" />
        <OwnerChip name={null} role="receiving_clinician" />
        <BPReading systolic={152} diastolic={96} />
        <BPReading systolic={185} diastolic={115} size="xl" />
      </div>
      <p>
        {t("states.RESULT_ISSUED")}: <BPReading systolic={164} diastolic={102} size="sm" />
      </p>
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard label={t("states.NOTIFIED")} value={<bdi dir="ltr">{t("units.hour", { count: 18 })}</bdi>} sub={<bdi dir="ltr">p90 {t("units.hour", { count: 30 })}</bdi>} n={42} />
        <StatCard label={t("states.CLOSED")} value={<bdi dir="ltr">64%</bdi>} n={12} />
        <StatCard label={t("states.REFERRED")} suppressed />
      </div>

      <h3 className={h}>Card, Tabs</h3>
      <Card title={t("timeline.title")} action={<Badge tone="accent">{t("simulated")}</Badge>}>
        <Tabs
          label={t("nav.queue")}
          value={tab}
          onChange={setTab}
          tabs={(["urgent", "overdue", "rejected", "unowned", "escalated", "all"] as const).map((q, i) => ({
            id: q,
            label: t(`queues.${q}`),
            count: i + 1,
          }))}
        />
      </Card>

      <h3 className={h}>Table</h3>
      <Table caption={t("nav.queue")} columns={cols} rows={ROWS} rowKey={(r) => r.id} onRowClick={() => toast.show(t("generic.view"))} />
      <Table caption={t("nav.queue")} columns={cols} rows={[]} rowKey={(r) => r.id} />

      <h3 className={h}>JourneySteps, Timeline</h3>
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <JourneySteps
            currentState="REFERRED"
            steps={CASE_STATES.map((s, i) => ({ state: s, done_at: i < 4 ? iso(-100 + i * 10) : null }))}
          />
        </Card>
        <Card>
          <Timeline events={EVENTS} />
        </Card>
      </div>

      <h3 className={h}>Field, Input, Select, Textarea, RadioGroup</h3>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("actions.add_reading")} hint={t("units.mmHg")}>
          <Input inputMode="numeric" placeholder="152" />
        </Field>
        <Field label={t("landing.region")} error={t("generic.required")}>
          <Select
            placeholder={t("generic.select")}
            options={[
              { value: "abu_dhabi", label: t("regions.abu_dhabi") },
              { value: "yaounde", label: t("regions.yaounde") },
            ]}
          />
        </Field>
        <Field label={t("actions.close")} optional>
          <Textarea />
        </Field>
        <RadioGroup
          name={`method-${t("nav.home")}`}
          legend={t("actions.choose_confirmation")}
          value={radio}
          onChange={setRadio}
          options={[
            { value: "HBPM", label: "HBPM" },
            { value: "ABPM", label: "ABPM", description: t("units.mmHg") },
          ]}
        />
      </div>

      <h3 className={h}>Loading, EmptyState, ErrorState</h3>
      <div className="grid gap-4 sm:grid-cols-3">
        <Loading />
        <EmptyState />
        <ErrorState error={{ status: 409, code: "invalid_state", message: "The case is not in a state that allows this action." }} onRetry={() => undefined} />
      </div>
      <ErrorState error={{ status: 0, code: "network_error", message: "backend_unreachable" }} />

      <h3 className={h}>Modal, Drawer, ConfirmDialog, Toast, JsonViewer</h3>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={() => setModal(true)}>
          Modal
        </Button>
        <Button variant="secondary" onClick={() => setDrawer(true)}>
          Drawer
        </Button>
        <Button variant="secondary" onClick={() => setConfirm(true)}>
          ConfirmDialog
        </Button>
        <Button variant="secondary" onClick={() => toast.show(t("demo.resetDone"))}>
          Toast
        </Button>
      </div>
      <Modal open={modal} onClose={() => setModal(false)} title={t("actions.close")} footer={<Button onClick={() => setModal(false)}>{t("generic.close")}</Button>}>
        <p>{t("demo.resetConfirmBody")}</p>
      </Modal>
      <Drawer open={drawer} onClose={() => setDrawer(false)} title="FHIR">
        <JsonViewer data={SAMPLE_JSON} />
      </Drawer>
      <ConfirmDialog
        open={confirm}
        title={t("demo.resetConfirmTitle")}
        body={t("demo.resetConfirmBody")}
        onCancel={() => setConfirm(false)}
        onConfirm={() => setConfirm(false)}
      />
      <JsonViewer data={SAMPLE_JSON} />
    </div>
  );
}

function LanguageSection({ lng }: { lng: Language }) {
  const inst = useMemo(() => i18n.cloneInstance({ lng }), [lng]);
  const dir = lng === "ar" ? "rtl" : "ltr";
  return (
    <I18nextProvider i18n={inst}>
      <section lang={lng} dir={dir} aria-label={lng} className="mt-8 rounded-card border-2 border-accent/40 bg-bg p-4">
        <h2 className="text-xl font-semibold">{lng.toUpperCase()}</h2>
        <Showcase />
      </section>
    </I18nextProvider>
  );
}

/** Renders every shared component in all three languages. Route: /kitchen-sink (not in navigation). */
export default function KitchenSink() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Kitchen sink</h1>
      <p className="text-muted">Every shared component, once per language. Arabic renders right to left.</p>
      <div className="mt-3">
        <LanguageSwitch />
      </div>
      {LANGUAGES.map((l) => (
        <LanguageSection key={l} lng={l} />
      ))}
    </div>
  );
}
