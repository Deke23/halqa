# Front-end shell guide

For the feature workstreams. Everything here is in `frontend/src`. Product name: import `APP_NAME` from `@/config`, never type it.
Use the `@/` alias for imports (`@/components`, `@/api/hooks`, `@/lib/format`).

Run: `npm run dev` (port 5173, proxies `/api` to `http://localhost:8000`), `npm run build` (type check plus bundle to `dist`), `npm run gen:api` (writes `src/api/schema.d.ts` from `../docs/openapi.json`).
Visual check of every component in all three languages: open `/kitchen-sink` (hidden from navigation, works signed out).

## How to add a page

Your feature folder already has an `index.tsx` with a default export. Replace its body.

| Route | File you own | Layout (already applied) | Roles |
|---|---|---|---|
| `/patient/*` | `features/patient/index.tsx` | `PatientLayout` | patient |
| `/phone/*` | `features/phone/index.tsx` | `PhoneThreadLayout` | patient |
| `/staff/queue` | `features/staff/queue/index.tsx` | `StaffLayout` | coordinator |
| `/staff/cases/:id` | `features/staff/case/index.tsx` | `StaffLayout` | coordinator, clinician |
| `/staff/worklist` | `features/staff/worklist/index.tsx` | `StaffLayout` | clinician |
| `/dashboard` | `features/dashboard/index.tsx` | `StaffLayout` | coordinator, clinician, analyst |
| `/transparency` | `features/transparency/index.tsx` | public, no login needed | everyone |

- `/patient/*` and `/phone/*` are splat routes. Inside your component use nested `<Routes>`, with paths relative to `/patient`, for example `<Route path="result" ... />`. Link with `to="/patient/result"`.
- A new staff screen: add a lazy import and a `<Route>` in `src/App.tsx` inside the `StaffLayout` group, wrapped in a `RoleGuard`, and an entry in the `NAV` array in `src/layouts/StaffLayout.tsx`. Those two files are the only shell files you should touch.
- Pages are lazy loaded and wrapped in Suspense by the layouts. Do not add your own `<main>`; the layout provides it.
- `RequireAuth` and `RoleGuard` are already applied. Persona to home mapping lives in `src/routes/personas.ts`. A wrong role is sent to its own home.

## Layouts (`src/layouts`)

- `AppShell`: root. Skip link, the demo bar (signed in, not on `/`), Suspense.
- `PatientLayout`: mobile first. Full width on a phone, a 480 px phone frame on desktop. Header shows the app name and the Simulated tag. Content area scrolls.
- `StaffLayout`: desktop, side navigation filtered by role.
- `PhoneThreadLayout`: handset frame, 380 px wide, fixed height. Your thread should be a flex column that fills it (a scrolling message list and a fixed reply box).
- `PublicLayout`: for pages that work signed out.

## Components (`@/components`)

All are keyboard reachable, RTL safe, typed. Spacing and alignment use logical classes (`ps-`, `pe-`, `ms-`, `me-`, `start-`, `end-`, `text-start`, `text-end`). Never write `pl-`, `pr-`, `ml-`, `mr-`, `left-`, `right-`, `text-left`, `text-right`.

| Component | Props | Example |
|---|---|---|
| `Button` | `variant` primary, secondary, ghost, danger; `size` sm, md, lg; `loading`; `fullWidth`; all button attributes | `<Button loading={m.isPending} onClick={go}>{t("generic.save")}</Button>` |
| `Card` | `title?`, `action?`, `padded?`, `as?` | `<Card title="Readings" action={<Badge>3</Badge>}>...</Card>` |
| `Badge` | `tone` neutral, accent, due, urgent, info | `<Badge tone="accent">Done</Badge>` |
| `Tag` | span attributes | `<Tag>Abu Dhabi</Tag>` |
| `SimulatedTag` | `label?` | `<SimulatedTag />` on every screen showing a simulated source (IFHAS, Thiqa, Malaffi, SMS, WhatsApp, cover lines, simulation results) |
| `Tabs` | `tabs: {id, label, count?}[]`, `value`, `onChange`, `label`, `panelId?` | `<Tabs label="Queues" tabs={tabs} value={q} onChange={setQ} />` |
| `Table` | `columns: {key, header, cell, numeric?}[]`, `rows`, `rowKey`, `caption`, `onRowClick?`, `empty?` | `<Table caption="Cases" columns={cols} rows={rows} rowKey={r => r.id} onRowClick={open} />` |
| `Modal` | `open`, `onClose`, `title`, `footer?`, `size?` | `<Modal open={o} onClose={close} title="Close case" footer={btns}>...</Modal>` |
| `Drawer` | `open`, `onClose`, `title`, `width?` md, lg, xl | `<Drawer open={o} onClose={close} title="FHIR"><JsonViewer data={b} /></Drawer>` |
| `ToastProvider`, `useToast()` | `show(message, tone?)` | `const toast = useToast(); toast.show(t("demo.resetDone"))` |
| `Field` | `label`, one control as child, `hint?`, `error?`, `required?`, `optional?` | `<Field label="Systolic" error={err}><Input inputMode="numeric" /></Field>` |
| `Input`, `Textarea` | native attributes | `<Input value={v} onChange={e => setV(e.target.value)} />` |
| `Select` | `options: {value, label}[]`, `placeholder?` | `<Select options={opts} placeholder="Choose" />` |
| `RadioGroup` | `name`, `legend`, `options: {value, label, description?, disabled?}[]`, `value`, `onChange`, `error?`, `inline?` | `<RadioGroup name="m" legend="Method" options={o} value={m} onChange={setM} />` |
| `Loading` | `label?` | `if (q.isLoading) return <Loading />` |
| `EmptyState` | `title?`, `description?`, `action?` | `<EmptyState description="No cases in this queue" />` |
| `ErrorState` | `error` (ApiError, Error or string), `title?`, `onRetry?` | `if (q.error) return <ErrorState error={q.error} onRetry={q.refetch} />` |
| `DueChip` | `dueAt`, `overdue?`, `now?`, `audience` staff or patient | `<DueChip dueAt={c.next_step.due_at} overdue={c.next_step.overdue} />` |
| `OwnerChip` | `name`, `role` | `<OwnerChip name={o?.name} role={o?.role} />` shows "No owner" when name is empty |
| `StateBadge` | `state` | `<StateBadge state={c.state} />` |
| `JourneySteps` | `currentState`, `steps?` (done_at per state), `labels?` | `<JourneySteps currentState={c.state} steps={c.progress} />` |
| `Timeline` | `events`, `eventLabel?`, `order?` | `<Timeline events={c.timeline ?? []} eventLabel={ev => t("staff:events." + ev.type)} />` |
| `StatCard` | `label`, `value`, `sub?`, `n?`, `suppressed?` | `<StatCard label="Median" value="18 h" n={m.n} suppressed={m.suppressed} />` |
| `BPReading` | `systolic`, `diastolic`, `size?` sm, md, xl, `hideUnit?` | `<BPReading systolic={152} diastolic={96} />` |
| `JsonViewer` | `data`, `defaultDepth?` | `<JsonViewer data={bundle} />` |
| `ConfirmDialog` | `open`, `title`, `body`, `onConfirm`, `onCancel`, `confirmLabel?`, `loading?`, `destructive?` | `<ConfirmDialog open={o} title="..." body="..." onConfirm={go} onCancel={close} />` |
| `LanguageSwitch` | `compact?` | `<LanguageSwitch compact />` |
| `DemoBar` | none | rendered by `AppShell`; do not render it yourself |
| `Placeholder` | `title`, `owner`, `route` | delete it when your screen exists |

Helpers: `useErrorText()` turns any error into display text, `useStateLabel()` and `useDurationText()` give translated labels, `cx()` joins class names (`@/lib/cx`).

## API hooks (`@/api/hooks`)

Types are loose until `npm run gen:api` has run. Each hook accepts a type argument (`useCase<MyDetail>(id)`). To adopt generated types, edit the aliases in `src/api/types.ts` to point at `components["schemas"][...]` from `schema.d.ts`; the hooks do not change.

| Hook | Route |
|---|---|
| `useMe()` | GET /me |
| `useConfig()` | GET /config (public) |
| `useCases(queue, region)` | GET /cases?queue=&region= |
| `useCase(id)` | GET /cases/{id} |
| `useMyCase()` | GET /my/case |
| `useSlots(id)` | GET /cases/{id}/slots |
| `useFhir(id, enabled)` | GET /cases/{id}/fhir (pass `enabled=drawerOpen`) |
| `useCaseAction(id)` | POST /cases/{id}/actions. `mutate({action, payload})`. Updates the cached detail and refreshes all case, dashboard and message queries |
| `useCreateEconsult(id)`, `useReplyEconsult()` | POST e-consult routes |
| `useDraftMessage(id)`, `useSendMessage(id)` | POST /cases/{id}/messages/draft and /send |
| `useMyMessages()`, `useReplyMessage()` | GET /my/messages (polls every 4 s), POST /my/messages/reply |
| `useIntakeResult()` | POST /intake/result |
| `useDashboardLive(split, region)`, `useDashboardSimulation(split)` | GET /dashboard/live and /simulation |
| `useDemoClock()`, `useDemoNow()`, `useAdvanceClock()`, `useResetDemo()` | demo clock and reset |

Errors are normalised to `{status, code, message}` (`isApiError`). `status` 0 means the backend could not be reached. A 401 clears the session and returns to the landing page. Show errors with `<ErrorState error={...} />` or `toast.show(errorText(e), "due")`.
Use `useDemoNow()`, not `new Date()`, whenever you decide overdue or due soon on screen.
Auth: `useAuth()` gives `{user, persona, isSignedIn, loginAsGuest, logout}`. `user.role` is patient, coordinator, clinician or analyst.

## i18n

- Languages `en`, `ar`, `fr`. Namespaces `common`, `patient`, `staff`, `dashboard`. Files: `src/i18n/locales/<lng>/<ns>.json`. Add every new key to all three languages in the same change.
- Use `useTranslation()` for `common`, `useTranslation("patient")` for a feature namespace. Cross-namespace: `t("common:states.NOTIFIED")` or `t("states.NOTIFIED")` from the default namespace.
- Already in `common`: nav, demo bar, personas, regions, the eight `states.*`, `roles.*`, `queues.*`, `actions.*`, `due.*`, `units.*`, `simulated`, `fewerThan5`, `generic.*`.
- Text rules: plain sentences, no em-dashes, no arrows, no marketing words. A screening reading is "a raised reading that needs checking", never a diagnosis. Arabic is Modern Standard Arabic in a respectful register. French uses "vous".
- `lang` and `dir` on `<html>` follow the language automatically. Do not set them yourself, except on a block of text that is in a different language from the page.
- Clinical values (blood pressure, pulse, dates, counts) are Latin digits in every language. Use `BPReading` for blood pressure, and `formatDate`, `formatDateTime`, `formatNumber` from `@/lib/format`, which force Latin digits. For any other number inside Arabic text wrap it in `<bdi dir="ltr">` or use the `.clinical` class.
- Never hard-code the product name. Never hard-code user-facing strings in components.

## Colour rules

Tokens are defined once in `src/index.css`. Use the Tailwind names: `bg-bg`, `bg-surface`, `bg-surface-2`, `border-line`, `text-ink`, `text-muted`, `bg-accent`, `bg-accent-soft`, `text-accent-ink`, `bg-due-soft`, `text-due-ink`, `bg-urgent-soft`, `text-urgent-ink`, `bg-info-soft`, `text-info-ink`. Do not introduce raw hex values or other palettes. All listed text and background pairs meet WCAG AA.

- Teal (`accent`) is the only accent.
- Amber (`due`) means due soon, or "needs attention" in a gentle way. Form validation errors use amber too.
- Red (`urgent`, `Button variant="danger"`, `Badge tone="urgent"`, `DueChip audience="staff"` when overdue) is only for clinical urgency on staff screens: severe readings, overdue cases, escalations. No red anywhere on patient screens, and none on lifestyle screens. On patient screens pass `audience="patient"` to `DueChip`.
- Never rely on colour alone: every chip carries text.
- No streaks, no loss framing, no failure states in the patient app.

## Misc

- Session token and user are in `sessionStorage` (wrapped in try and catch). Language is in `localStorage`.
- Personas set a default language on sign in (Khalid Arabic, Jean-Paul and Clarisse French, others English). The user can change it with `LanguageSwitch`.
- Small-cell suppression: show a suppressed dashboard cell with `StatCard suppressed`, which prints "fewer than 5" in the active language.
