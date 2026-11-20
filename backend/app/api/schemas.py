"""Request and response schemas. Named models and enums so the OpenAPI file is precise."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.engine.types import (
    Action,
    CheckinStatus,
    ClosureEvidence,
    ConfirmationMethod,
    ConfirmationStatus,
    EventType,
    PlanActionKey,
    PlanSize,
    ReadingSource,
    ReferralStatus,
    Severity,
    State,
)

__all__ = ["Action", "State"]


class Region(StrEnum):
    AUH = "AUH"
    YDE = "YDE"


class Language(StrEnum):
    EN = "en"
    AR = "ar"
    FR = "fr"


class Channel(StrEnum):
    APP = "APP"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"


class RoleName(StrEnum):
    PATIENT = "patient"
    COORDINATOR = "coordinator"
    CLINICIAN = "clinician"
    ANALYST = "analyst"


class PersonaKey(StrEnum):
    PATIENT_AUH = "patient_auh"
    COORDINATOR_AUH = "coordinator_auh"
    CLINICIAN_PCP = "clinician_pcp"
    CLINICIAN_SPECIALIST = "clinician_specialist"
    PATIENT_YDE = "patient_yde"
    NURSE_YDE = "nurse_yde"
    ANALYST = "analyst"
    CLINICIAN_YDE = "clinician_yde"
    SPECIALIST_YDE = "specialist_yde"


class QueueName(StrEnum):
    ALL = "all"
    URGENT = "urgent"
    OVERDUE = "overdue"
    REJECTED = "rejected"
    UNOWNED = "unowned"
    ESCALATED = "escalated"
    MINE = "mine"


class Split(StrEnum):
    NONE = "none"
    LANGUAGE = "language"
    NATIONALITY_GROUP = "nationality_group"
    SEX = "sex"
    AGE_BAND = "age_band"


class ConsentPurpose(StrEnum):
    CARE_COORDINATION = "care_coordination"
    MESSAGING_CHANNEL = "messaging_channel"
    SHARE_WITH_RECEIVING_PROVIDER = "share_with_receiving_provider"
    LIFESTYLE_PROGRAMME = "lifestyle_programme"
    RESEARCH_AGGREGATE = "research_aggregate"


class RedFlag(StrEnum):
    CHEST_PAIN = "chest_pain"
    SHORTNESS_OF_BREATH = "shortness_of_breath"
    SEVERE_HEADACHE = "severe_headache"
    VISION_CHANGE = "vision_change"
    CONFUSION = "confusion"
    ONE_SIDED_WEAKNESS = "one_sided_weakness"
    UNSPECIFIED = "unspecified"  # a "yes" to the phone-thread red-flag question, which does not say which symptom


class Barrier(StrEnum):
    TIME = "TIME"
    COST = "COST"
    NOT_SURE_HOW = "NOT_SURE_HOW"
    FELT_UNWELL = "FELT_UNWELL"
    WORK_SCHEDULE = "WORK_SCHEDULE"
    OTHER = "OTHER"


class MessageSource(StrEnum):
    TEMPLATE = "TEMPLATE"
    AI_REWORDED = "AI_REWORDED"


class ReviewOutcome(StrEnum):
    CONFIRMED = "CONFIRMED"
    NOT_CONFIRMED = "NOT_CONFIRMED"


class VisitOutcome(StrEnum):
    TREATMENT_STARTED = "TREATMENT_STARTED"
    SURVEILLANCE = "SURVEILLANCE"


class IntakeSource(StrEnum):
    IFHAS_SCREENING = "IFHAS_SCREENING"
    CLINIC_READING = "CLINIC_READING"
    OTHER = "OTHER"


class ErrorResponse(BaseModel):
    code: str
    message: str


# ---------------------------------------------------------------- auth and users


class I18nText(BaseModel):
    """The same display text in every supported language. The front end picks the key for its current language."""

    en: str
    ar: str
    fr: str


class PersonRef(BaseModel):
    """A person shown to a reader. `name` has no role in brackets; `role` is the job title, for example `nurse coordinator`."""

    name: str
    role: str
    names: I18nText  # the name without a role in brackets, in en, ar and fr
    roles: I18nText  # the job title in en, ar and fr


class UserOut(BaseModel):
    id: int
    persona: PersonaKey | None
    name: str  # kept for compatibility, may carry the role in brackets, for example `Clarisse (nurse coordinator)`
    display_name: str  # the same person without the role in brackets
    role_title: str  # the job title from the brackets, or the access role when there is none
    display_names: I18nText
    role_titles: I18nText
    organisation_i18n: I18nText
    role: RoleName
    region: Region
    organisation: str
    language: Language
    patient_id: int | None
    description: str


class GuestRequest(BaseModel):
    persona: PersonaKey


class AuthResponse(BaseModel):
    token: str
    user: UserOut


# ---------------------------------------------------------------- action payloads


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyPayload(_Payload):
    pass


class NotifyPayload(_Payload):
    template_id: str
    language: Language
    channel: Channel


class AcknowledgePayload(_Payload):
    teach_back_answer: str
    red_flags: list[RedFlag] = Field(default_factory=list)
    confidence: int | None = Field(default=None, ge=1, le=5)


class ChooseConfirmationPayload(_Payload):
    method: ConfirmationMethod


class AddReadingPayload(_Payload):
    systolic: int = Field(ge=60, le=300)
    diastolic: int = Field(ge=30, le=200)
    pulse: int | None = Field(default=None, ge=20, le=250)
    taken_at: datetime
    source: ReadingSource


class ReviewConfirmationPayload(_Payload):
    outcome: ReviewOutcome
    note: str | None = None


class ReferPayload(_Payload):
    to_user_id: int | None = None
    to_service: str | None = None
    reason: str = Field(min_length=3)


class ReasonPayload(_Payload):
    reason: str = Field(min_length=3)


class AssignOwnerPayload(_Payload):
    user_id: int


class BookAppointmentPayload(_Payload):
    slot_id: int


class RecordVisitPayload(_Payload):
    outcome: VisitOutcome
    note: str | None = None


class PlanCheckinPayload(_Payload):
    status: CheckinStatus
    barrier: Barrier | None = None
    accept_larger: bool = False


class ClosePayload(_Payload):
    """Fields are optional here so the closure gate, not the schema, explains what is missing."""

    evidence_type: ClosureEvidence | None = None
    evidence_ref: str | None = None
    decision_note: str | None = None


class UrgentReviewPayload(_Payload):
    note: str = Field(min_length=3)


class ConsentPayload(_Payload):
    purpose: ConsentPurpose
    granted: bool
    channel: Channel | None = None


PAYLOAD_MODELS: dict[Action, type[BaseModel]] = {
    Action.NOTIFY: NotifyPayload,
    Action.ACKNOWLEDGE: AcknowledgePayload,
    Action.CHOOSE_CONFIRMATION: ChooseConfirmationPayload,
    Action.ADD_READING: AddReadingPayload,
    Action.REVIEW_CONFIRMATION: ReviewConfirmationPayload,
    Action.REFER: ReferPayload,
    Action.ACCEPT_REFERRAL: EmptyPayload,
    Action.REJECT_REFERRAL: ReasonPayload,
    Action.ASSIGN_OWNER: AssignOwnerPayload,
    Action.BOOK_APPOINTMENT: BookAppointmentPayload,
    Action.RECORD_VISIT: RecordVisitPayload,
    Action.PLAN_CHECKIN: PlanCheckinPayload,
    Action.ESCALATE: ReasonPayload,
    Action.CLOSE: ClosePayload,
    Action.REOPEN: ReasonPayload,
    Action.UPDATE_CONSENT: ConsentPayload,
    Action.COMPLETE_URGENT_REVIEW: UrgentReviewPayload,
}


class ActionRequest(BaseModel):
    """`payload` is validated against the model for `action` (see components.schemas *Payload) after role and state checks."""

    action: Action
    payload: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------- case detail


class PatientSummary(BaseModel):
    id: int
    ref: str
    display_name: str
    initials: str
    age: int
    sex: str
    nationality_group: str
    language: Language
    region: Region
    insurance: str
    channel: Channel
    organisation: str
    names: I18nText
    initials_i18n: I18nText
    organisation_i18n: I18nText
    region_name_i18n: I18nText


class NextStepOut(BaseModel):
    label_key: str
    owner_role: RoleName
    acting_role: RoleName
    owner_user_id: int | None
    owner_name: str | None
    owner_person: PersonRef | None
    started_at: datetime
    due_at: datetime
    service_level_h: float
    overdue: bool
    overdue_hours: float
    escalation_level: int
    escalation_target: str | None


class ProgressStep(BaseModel):
    state: State
    label_key: str
    reached: bool
    current: bool
    reached_at: datetime | None


class ReadingOut(BaseModel):
    id: int
    systolic: int
    diastolic: int
    pulse: int | None
    taken_at: datetime
    source: ReadingSource
    entered_by_role: str


class ConfirmationOut(BaseModel):
    method: ConfirmationMethod | None
    status: ConfirmationStatus | None
    average_systolic: float | None
    average_diastolic: float | None
    days_counted: int
    readings_used: int
    days_with_enough_readings: int
    days_required: int
    threshold_status: str


class ReferralOut(BaseModel):
    id: int
    status: ReferralStatus
    to_user_id: int | None
    to_name: str | None
    to_person: PersonRef | None
    to_service: str | None
    to_service_i18n: I18nText | None
    from_name: str | None
    from_person: PersonRef | None
    reason: str
    rejection_reason: str | None
    created_at: datetime
    decided_at: datetime | None


class AppointmentOut(BaseModel):
    id: int
    starts_at: datetime
    provider_name: str
    location: str
    status: str
    provider_name_i18n: I18nText
    provider_person: PersonRef
    location_i18n: I18nText
    label_i18n: I18nText  # date and time on the region clock, provider and place, per language


class ReplyOption(BaseModel):
    """One reply the patient can send now. `meaning_key` is for the front end's own label (reply.yes, reply.option_a, ...)."""

    reply: str
    meaning_key: str


class MessageOut(BaseModel):
    id: int
    direction: Literal["OUT", "IN"]
    channel: Channel
    language: Language
    text: str
    template_id: str | None
    template_version: str | None
    source: MessageSource
    sender_name: str | None
    sender_person: PersonRef | None
    approved_by_name: str | None
    approved_by_person: PersonRef | None
    created_at: datetime
    valid_replies: list[ReplyOption] = []  # only on the latest outbound message of an open case, for quick-reply buttons


class EConsultOut(BaseModel):
    id: int
    case_id: int
    from_user_id: int
    from_name: str
    from_person: PersonRef
    to_user_id: int
    to_name: str
    to_person: PersonRef
    question: str
    answer: str | None
    status: Literal["OPEN", "ANSWERED"]
    created_at: datetime
    answered_at: datetime | None


class PlanWeekOut(BaseModel):
    week_index: int
    action_key: PlanActionKey
    size: PlanSize
    status: CheckinStatus | None
    barrier: Barrier | None
    offered_larger: bool
    starts_at: datetime
    checked_in_at: datetime | None
    label_key: str
    default_text: str  # in the patient's language (or the requested `language`), from the approved templates
    default_text_i18n: I18nText


class ConsentOut(BaseModel):
    purpose: ConsentPurpose
    channel: Channel | None
    granted: bool
    granted_at: datetime | None
    withdrawn_at: datetime | None


class EventOut(BaseModel):
    id: int
    at: datetime
    actor_name: str
    actor_person: PersonRef | None
    actor_role: str
    type: EventType
    from_state: State | None
    to_state: State | None
    payload: dict[str, Any]
    reason: str | None


class TaskOut(BaseModel):
    id: int
    type: str
    title_key: str
    owner_role: RoleName
    owner_user_id: int | None
    due_at: datetime | None
    status: Literal["OPEN", "DONE"]
    overdue: bool
    created_at: datetime
    title_i18n: I18nText


class ClosureOut(BaseModel):
    closed_at: datetime
    closed_by_name: str | None
    closed_by_person: PersonRef | None
    evidence_type: ClosureEvidence
    evidence_ref: str | None
    decision_note: str | None


class EmergencyAdvice(BaseModel):
    text: str
    text_i18n: I18nText
    number: str | None
    region: Region


class Feedback(BaseModel):
    code: str
    message: str
    template_id: str | None = None


class CaseFlags(BaseModel):
    overdue: bool
    unowned: bool
    rejected: bool
    escalated: bool
    needs_clinician_decision: bool
    closure_ready: bool
    urgent_review_pending: bool
    care_coordination_withdrawn: bool = False


class TeachBackOut(BaseModel):
    """The teach-back question as structured fields in one language. The front end never parses message text."""

    question: str  # no "reply 1, 2 or 3" sentence in the app variant
    options: list[str]  # answer with the 1-based option number
    simpler: str  # shown after a wrong answer
    language: Language


class CaseDetail(BaseModel):
    id: int
    state: State
    severity: Severity
    urgent: bool
    urgent_reason: str | None
    region: Region
    opened_at: datetime
    index_systolic: int
    index_diastolic: int
    source_system: str
    patient: PatientSummary
    owner_role: RoleName
    owner_user_id: int | None
    owner_name: str | None
    owner_person: PersonRef | None
    urgent_review_due_at: datetime | None  # due time of the open urgent review task; null when none or done (staff view)
    plan_active: bool  # false while the lifestyle programme is withdrawn: no weekly actions or check-ins
    next_step: NextStepOut | None
    progress: list[ProgressStep]
    flags: CaseFlags
    referral_status: ReferralStatus | None
    suggested_closure_type: ClosureEvidence | None
    readings: list[ReadingOut]
    confirmation: ConfirmationOut | None
    referral: ReferralOut | None
    referrals_history: list[ReferralOut]
    appointment: AppointmentOut | None
    messages: list[MessageOut]
    econsults: list[EConsultOut]
    plan: list[PlanWeekOut]
    consents: list[ConsentOut]
    tasks: list[TaskOut]
    timeline: list[EventOut]
    closure: ClosureOut | None
    allowed_actions: list[Action]
    emergency_advice: EmergencyAdvice | None
    teach_back: TeachBackOut | None = None
    feedback: Feedback | None = None
    view: Literal["STAFF", "PATIENT"]


class CaseSummary(BaseModel):
    id: int
    patient_initials: str
    patient_ref: str
    region: Region
    language: Language
    state: State
    severity: Severity
    urgent: bool
    owner_role: RoleName
    owner_user_id: int | None
    owner_name: str | None
    owner_person: PersonRef | None
    patient_names: I18nText
    patient_initials_i18n: I18nText
    age_band: str
    next_step_label_key: str | None
    due_at: datetime | None
    overdue: bool
    overdue_hours: float
    escalation_level: int
    reason_code: str
    reason_text: str  # includes the rejection reason or the escalation reason when there is one
    rejection_reason: str | None  # the receiving clinician's reason, only while the referral is rejected
    escalation_reason: str | None  # the reason given on the latest escalation, or the automatic one
    last_contact_attempt_at: datetime | None
    last_contact_attempt: str | None  # MESSAGE_SENT, MESSAGE_SUPPRESSED or the unreachable-protocol step
    flags: CaseFlags
    index_systolic: int
    index_diastolic: int
    opened_at: datetime


class CaseList(BaseModel):
    queue: QueueName
    total: int
    cases: list[CaseSummary]


# ---------------------------------------------------------------- slots, econsults, messages


class CoverOut(BaseModel):
    covered: bool | None
    copay: float | None
    estimated_price: float | None
    currency: str
    label: str
    label_i18n: I18nText  # every language says it is simulated
    simulated: Literal[True] = True
    simulated_label_i18n: I18nText


class SlotOut(BaseModel):
    id: int
    starts_at: datetime
    provider_name: str
    location: str
    cover: CoverOut
    provider_name_i18n: I18nText
    provider_person: PersonRef
    location_i18n: I18nText
    label_i18n: I18nText


class EConsultCreate(BaseModel):
    to_user_id: int
    question: str = Field(min_length=3)


class EConsultReply(BaseModel):
    answer: str = Field(min_length=3)


class DraftRequest(BaseModel):
    template_id: str
    language: Language
    tone: str | None = None
    channel: Channel | None = None  # default: the patient's channel


class DraftOut(BaseModel):
    id: int  # the server-stored draft; send takes this id, never text
    channel: Channel
    text: str
    source: MessageSource
    template_id: str
    template_version: str
    language: Language
    validation: dict[str, Any]


class SendRequest(BaseModel):
    """Send a stored draft. Free text is refused: the server re-renders the template and re-validates AI wording."""

    model_config = ConfigDict(extra="forbid")

    draft_id: int
    approve: bool = False  # required (true) for an AI re-worded draft; the approver is the signed-in staff member


class SendResponse(BaseModel):
    message: MessageOut


class ReplyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class IntakeReading(BaseModel):
    systolic: int = Field(ge=60, le=300)
    diastolic: int = Field(ge=30, le=200)
    pulse: int | None = None
    taken_at: datetime | None = None


class NewPatient(BaseModel):
    display_name: str
    age: int = Field(ge=18, le=110)
    sex: Literal["F", "M"]
    nationality_group: str = "Other"
    language: Language = Language.EN
    insurance: str = "NONE"
    channel: Channel = Channel.APP


class IntakeRequest(BaseModel):
    patient_ref: str
    source_system: IntakeSource
    region: Region
    readings: list[IntakeReading] = Field(min_length=1)
    patient: NewPatient | None = None


class IntakeResponse(BaseModel):
    opened: bool
    case_id: int | None
    severity: Severity | None
    reason: str


# ---------------------------------------------------------------- dashboard


class DelayReason(BaseModel):
    reason: str
    n: int
    suppressed: bool


class Measure(BaseModel):
    name: str
    unit: str
    n: int
    suppressed: bool
    value: float | None = None
    median: float | None = None
    p90: float | None = None
    count: int | None = None
    delay_reasons: list[DelayReason] | None = None


class DashboardGroup(BaseModel):
    key: str
    label: str
    label_i18n: I18nText
    measures: list[Measure]


class DashboardLive(BaseModel):
    split: Split
    region: Region | None
    generated_at: datetime
    simulated: Literal[False] = False
    min_cell_size: int
    groups: list[DashboardGroup]


class SimulationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    available: bool


# ---------------------------------------------------------------- demo, config, health


class ClockOut(BaseModel):
    now: datetime
    real_now: datetime
    offset_seconds: float


class AdvanceRequest(BaseModel):
    hours: float = Field(gt=0, le=24 * 60)


class ResetResponse(BaseModel):
    reset: bool
    cases: int
    clock: ClockOut


class ConfigEntryOut(BaseModel):
    section: str
    key: str
    value: Any
    unit: str
    basis: str
    status: str
    label_i18n: I18nText
    basis_i18n: I18nText
    unit_i18n: I18nText


class ClosureEvidenceLabel(BaseModel):
    code: ClosureEvidence
    label_i18n: I18nText


class RegionConfig(BaseModel):
    region: Region
    name: str
    name_i18n: I18nText
    default_language: Language
    languages: list[Language]
    emergency_text: dict[str, str]
    emergency_number: str | None
    timezone: str


class ConfigOut(BaseModel):
    app_name: str
    demo_mode: bool  # false: guest login, clock advance, reset and the intake simulator are disabled
    notice: str
    entries: list[ConfigEntryOut]
    closure_evidence_types: list[ClosureEvidence]
    closure_evidence_labels: list[ClosureEvidenceLabel]
    notice_i18n: I18nText
    rules_i18n: list[I18nText]
    templates: list[dict[str, Any]]
    languages: list[Language]
    regions: list[RegionConfig]
    rules: list[str]


class PersonaInfo(BaseModel):
    persona: PersonaKey
    name: str
    display_name: str
    role_title: str
    display_names: I18nText
    role_titles: I18nText
    role: RoleName
    region: Region
    description: str
    listed: bool = True  # false: a persona that exists but is not offered in the picker


class HealthOut(BaseModel):
    status: Literal["ok"]
    app: str
    now: datetime


class DiaryDay(BaseModel):
    day: int
    steps: int
    active_minutes: int
    sleep_hours: float
    sleep_efficiency_pct: int


class SampleReading(BaseModel):
    day: int
    time: str
    systolic: int
    diastolic: int
    pulse: int | None = None


class DiaryOut(BaseModel):
    """Wearable data is a diary only. wearable_used_for_bp is always false."""

    wearable_used_for_bp: Literal[False] = False
    wearable_days: list[DiaryDay]
    wearable_note: str
    hbpm_sample: list[SampleReading]
    abpm_sample: list[SampleReading]
    disclaimer: str
