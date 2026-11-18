# Halqa diagrams

All diagrams describe the prototype in `docs/SPEC.md`. People, readings, providers and messages are synthetic. Thresholds and service levels are placeholders pending clinician sign-off.

## 1. System architecture

The browser surfaces call one FastAPI app, whose engine is pure rules and never imports the wording module, and only the wording module may reach the optional LLM provider.

```mermaid
flowchart LR
    subgraph SPA ["Browser React SPA"]
        P["Patient app"]
        PS["Phone thread simulator"]
        CQ["Coordinator queue"]
        CW["Clinician worklist"]
        OD["Outcome dashboard"]
    end
    subgraph APP ["FastAPI app"]
        API["api HTTP routes and role checks"]
        ENG["engine case state machine SLA and closure gate pure no I/O never imports wording"]
        WORD["wording templates and validator"]
        FHIR["fhir R4 projection read only"]
        SIM["sim cohort and pathway simulation"]
        DEMO["demo clock seed and reset"]
        DB["db SQLAlchemy models and session"]
    end
    subgraph STORE ["Database"]
        SQLITE[("SQLite by default")]
        PG[("PostgreSQL when DATABASE_URL is set")]
    end
    subgraph EXT ["Simulated sources, sinks and optional provider"]
        IFHAS["Simulated IFHAS screening feed"]
        CLIN["Simulated clinic reading"]
        CHAN["Simulated SMS and WhatsApp channel"]
        LLM["Optional LLM provider for wording only"]
    end
    P --> API
    PS --> API
    CQ --> API
    CW --> API
    OD --> API
    API --> ENG
    API --> WORD
    API --> FHIR
    API --> SIM
    API --> DEMO
    API --> DB
    DB --> SQLITE
    DB -.->|"DATABASE_URL set"| PG
    IFHAS -->|"POST intake result"| API
    CLIN -->|"clinic reading"| API
    API <-->|"outbound messages and keyword replies"| CHAN
    WORD -.->|"optional reword, validated text only"| LLM
```

## 2. Case lifecycle

The case moves forward through the milestones in SPEC section 4.1, with the action that causes each move written on the transition, and only a clinician can enter CLOSED.

```mermaid
stateDiagram-v2
    [*] --> RESULT_ISSUED : actionable result received
    RESULT_ISSUED --> NOTIFIED : notify
    NOTIFIED --> ACKNOWLEDGED : acknowledge
    ACKNOWLEDGED --> ACKNOWLEDGED : choose_confirmation or add_reading
    ACKNOWLEDGED --> CONFIRMED : review_confirmation CONFIRMED
    ACKNOWLEDGED --> CLOSED : clinician close with NOT_CONFIRMED evidence
    CONFIRMED --> REFERRED : refer
    REFERRED --> CONFIRMED : reject_referral keeps case here with REJECTED status
    REFERRED --> APPOINTMENT_BOOKED : book_appointment
    APPOINTMENT_BOOKED --> IN_CARE : record_visit
    CLOSED --> IN_CARE : reopen, returns to previous state
    note right of ACKNOWLEDGED : review_confirmation NOT_CONFIRMED keeps the case here with a clinician closure decision due in 3 days
    note right of REFERRED : accept_referral sets referral to ACCEPTED
    note left of CONFIRMED : A rejected referral waits here until a coordinator reassigns or a clinician re-refers
    note right of IN_CARE : plan_checkin runs the weekly lifestyle action
    note right of CLOSED : Only a clinician can enter CLOSED. Any state reaches CLOSED through the close action. Reopen returns to the state held before closure, IN_CARE is drawn only as one example
```

## 3. Ownership and service levels

The table lists each case state with its next step, accountable owner role and default service level, copied from SPEC section 4.1.

| # | State | Next step | Accountable owner role | Default service level |
|---|---|---|---|---|
| 1 | `RESULT_ISSUED` | Notify the patient | coordinator | 24 h (2 h if severe) |
| 2 | `NOTIFIED` | Patient acknowledges and passes teach-back | coordinator | 72 h |
| 3 | `ACKNOWLEDGED` | Complete confirmation by home BP monitoring (HBPM) or ABPM and clinician review of the result | primary care clinician | 14 days |
| 4 | `CONFIRMED` | Send referral | primary care clinician | 3 days |
| 5 | `REFERRED` | Receiving clinician accepts, then appointment is booked | receiving clinician until accepted, then coordinator | 2 days to accept, 5 days to book |
| 6 | `APPOINTMENT_BOOKED` | Visit happens, outcome recorded | receiving clinician | appointment time plus 24 h |
| 7 | `IN_CARE` | Review at 4 weeks; weekly lifestyle action runs here | treating clinician | 28 days |
| 8 | `CLOSED` | none | none | none |

These values are placeholders pending clinician sign-off.

For severe cases a separate urgent_review task, owned by the clinician role and due in 4 hours, runs in parallel with the normal next step and escalates to the on-call clinician if not completed by its due time.

## 4. Severe reading escalation

A 185/115 reading is classed as severe by rule, which sets a 2 hour notification step and a parallel urgent review due in 4 hours that escalates to the on-call clinician if no clinician completes it in time.

```mermaid
sequenceDiagram
    participant F as "Simulated IFHAS feed"
    participant A as "API"
    participant E as "Engine"
    participant Q as "Coordinator queue"
    participant C as "Clinician"
    participant O as "On-call clinician"
    participant P as "Patient"
    F->>A: POST intake result with 185/115 reading
    A->>E: classify reading with now
    E-->>A: SEVERE by rule, systolic at or above 180
    A->>Q: open urgent case at top of queue
    E->>Q: patient notification step due in 2 hours
    A->>P: urgent template with red-flag symptom advice
    E->>Q: parallel urgent_review task due in 4 hours
    Q->>C: urgent_review task appears in clinician worklist
    alt Completed by a clinician before the due time
        C->>A: complete_urgent_review with note
    else Not completed by the due time
        E-->>Q: urgent_review escalates to on-call clinician
        Q->>O: task escalated to on-call clinician
    end
    Note over Q: Case stays urgent until a clinician completes complete_urgent_review
    Note over E,Q: Evaluation runs on every clock advance, on every case read and on a 60 second tick
```

## 5. Standard journey

The patient_auh persona goes from a 152/96 screening result through teach-back, home monitoring and referral to a weekly salt action, then a missed week and a no-blame check-in that makes the plan smaller.

```mermaid
sequenceDiagram
    participant S as "Engine and API"
    participant Co as "Coordinator"
    participant Pt as "Patient patient_auh"
    participant PCP as "Primary care clinician"
    participant RC as "Receiving clinician"
    Note over S: Demo starts at NOTIFIED so the result message is seen first
    S->>Co: case opened from simulated IFHAS result 152/96
    Co->>Pt: result message in Arabic or English with reading shown
    Pt->>S: acknowledge with teach-back answer and confidence
    Pt->>S: choose_confirmation HBPM
    loop Home readings
        Pt->>S: add_reading HOME_CUFF with running average
    end
    Note over S: HBPM average at or above 135/85 over at least 4 days, first day discarded, placeholder
    PCP->>S: review_confirmation CONFIRMED
    PCP->>S: refer to receiving clinician
    RC->>S: accept_referral
    Pt->>S: book_appointment after cover is shown, simulated
    RC->>S: record_visit TREATMENT_STARTED
    S->>Pt: weekly_action salt at full size
    Pt->>S: plan_checkin status missed
    S->>Pt: no_blame_checkin and plan_smaller for next week
    Note over Pt: No streak, no penalty and no red failure state
```

## 6. AI boundary

Every message starts from the deterministic template render, and model output can only enter through the optional reword and validator, while routing, urgency, ownership and closure never read it.

```mermaid
flowchart TD
    REQ["Staff requests a message draft with template id and language"]
    REN["Render approved template deterministically, the default path"]
    Q1{"Optional reword enabled by WORDING_PROVIDER"}
    subgraph AIB ["AI boundary: model output allowed only inside this box"]
        LLM["Optional LLM reword returns text only"]
        V1["Every slot number, date, time, name and phone unchanged"]
        V2["No new numbers"]
        V3["No diagnosis words from block list"]
        V4["Length within channel limit"]
        V5["Detected language matches requested language"]
        LLM --> V1 --> V2 --> V3 --> V4 --> V5
    end
    APP{"Staff approves AI reworded draft"}
    FB["Template fallback with validation failed_reason"]
    SEND["Message sent and event records source and approver"]
    subgraph OUT ["Outside the AI box: rules that never read model output"]
        ROUTE["Routing and urgency"]
        OWN["Ownership and service levels"]
        CLS["Closure gate"]
    end
    REQ --> REN --> Q1
    Q1 -->|"no"| SEND
    Q1 -->|"yes"| LLM
    V5 -->|"pass"| APP
    APP --> SEND
    V1 -->|"fail"| FB
    V2 -->|"fail"| FB
    V3 -->|"fail"| FB
    V4 -->|"fail"| FB
    V5 -->|"fail"| FB
    FB --> SEND
```

## 7. Closure gate

A close request succeeds only when the caller is a clinician and the evidence is complete, and no timer, job or rule ever sets a case to CLOSED.

```mermaid
flowchart TD
    REQ["Close requested with close action"]
    R1{"Caller role is clinician"}
    X1["Refuse: role may not close"]
    E1{"Evidence type present"}
    X2["Refuse: evidence type missing"]
    E2{"Evidence reference or decision note of at least 10 characters"}
    X3["Refuse: no reference or decision note"]
    CLS["Case set to CLOSED"]
    AUD["CaseEvent written with clinician id, time, evidence type and reference or note"]
    EVT["Allowed evidence types: BP_CONTROLLED, NOT_CONFIRMED, CARE_TRANSFERRED, PATIENT_DECLINED, UNREACHABLE_AFTER_PROTOCOL, DECEASED_OR_MOVED, OTHER_CLINICAL_DECISION"]
    STMT["No timer, job or rule ever sets a case to CLOSED"]
    REQ --> R1
    R1 -->|"no"| X1
    R1 -->|"yes"| E1
    E1 -->|"no"| X2
    E1 -->|"yes"| E2
    E2 -->|"no"| X3
    E2 -->|"yes"| CLS
    CLS --> AUD
    EVT -.-> E1
```
